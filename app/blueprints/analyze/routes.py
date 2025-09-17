import os
import shutil
import time
from typing import Dict
from flask import current_app, render_template, request, redirect, url_for, flash, send_file, jsonify
from werkzeug.utils import secure_filename

from . import bp
from app import db, DEFAULT_SETTINGS
from app.models import Contract, Analysis, Hit, Summary
from ...services.parser import parse_document, sha256_file
from ...services.inference import classify_text, inject_highlights, model_display_name, category_color
from ...services.summarizer import generate_overall_summary, generate_clause_explanation
from ...services.report import render_report_html, save_html_report, save_pdf_report
from ...services.pdf_highlight import generate_highlighted_pdf, compute_hit_rects



ALLOWED_EXT = {".pdf", ".docx"}


def allowed_file(filename: str) -> bool:
    _, ext = os.path.splitext(filename.lower())
    return ext in ALLOWED_EXT


@bp.route("/")
def upload_form():
    return render_template("analyze/upload.html")


@bp.route("/run", methods=["POST"])
def run_analysis():
    f = request.files.get("file")
    if not f or f.filename == "":
        flash("Please choose a file.", "warning")
        return redirect(url_for("analyze.upload_form"))
    if not f.filename or not allowed_file(f.filename):
        flash("Unsupported file type. Allowed: PDF or DOCX.", "danger")
        return redirect(url_for("analyze.upload_form"))

    config = current_app.config
    settings = getattr(current_app, "settings", config.get("SETTINGS", {}))
    upload_max = int(settings.get("upload_max_mb", 15)) * 1024 * 1024
    # Note: MAX_CONTENT_LENGTH provides a hard cap; this is a soft check
    f.stream.seek(0, os.SEEK_END)
    size = f.stream.tell()
    f.stream.seek(0)
    if size > upload_max:
        flash(f"File too large (> {settings.get('upload_max_mb', 15)} MB).", "danger")
        return redirect(url_for("analyze.upload_form"))

    filename = secure_filename(f.filename)
    save_path = os.path.join(config["UPLOAD_FOLDER"], f"{int(time.time())}_{filename}")
    f.save(save_path)

    file_hash = sha256_file(save_path)
    text, num_pages = parse_document(save_path)

    contract = Contract(filename=filename, path=save_path, file_hash=file_hash, num_pages=num_pages)
    db.session.add(contract)
    db.session.commit()

    # Inference
    model_spec = settings.get("model_name_or_path") or DEFAULT_SETTINGS.get("model_name_or_path")
    threshold = float(settings.get("threshold", 0.6))
    merge_window = int(settings.get("merge_window_chars", 80))
    spans = classify_text(text, model_spec, threshold=threshold, merge_window_chars=merge_window)

    # Persist analysis
    analysis = Analysis(
        contract_id=contract.id,
        model_name=model_display_name(model_spec),
        model_version="1.0",
        total_hits=len(spans),
    )
    db.session.add(analysis)
    db.session.flush()

    for sp in spans:
        db.session.add(Hit(
            analysis=analysis,
            category=sp.category,
            prob=sp.prob,
            page_no=sp.page_no or 0,
            start_char=sp.start,
            end_char=sp.end,
            text_excerpt=sp.text,
            ambiguous=sp.prob < (threshold + 0.05),
        ))
    db.session.commit()

    # Optional Gemini summary
    summary_text = ""
    if settings.get("enable_gemini", False):
        hits_by_cat: Dict[str, list] = {}
        for sp in spans:
            hits_by_cat.setdefault(sp.category, []).append(sp.text)
        summary_text = generate_overall_summary(hits_by_cat, model_name=settings.get("gemini_model", "gemini-2.0-flash"))
        db.session.add(Summary(analysis_id=analysis.id, output_text=summary_text))
        db.session.commit()

    return redirect(url_for("analyze.view_result", analysis_id=analysis.id))


@bp.route("/<int:analysis_id>")
def view_result(analysis_id: int):
    analysis = Analysis.query.get_or_404(analysis_id)
    contract = analysis.contract
    # Read full text again for preview
    try:
        with open(contract.path, "rb") as rf:
            data = rf.read()
        # decode if text, else reparse; for simplicity just parse again
        from ...services.parser import parse_document
        text, _ = parse_document(contract.path)
    except Exception:
        text = "(Unable to load source text. File moved or deleted.)"

    hits = Hit.query.filter_by(analysis_id=analysis.id).order_by(Hit.start_char.asc()).all()
    spans = []
    hit_index = {}
    for idx, h in enumerate(hits, start=1):
        hit_index[h.id] = idx
        color = category_color(h.category)
        setattr(h, "color", color)
        spans.append(type("S", (), dict(start=h.start_char, end=h.end_char, page_no=h.page_no, category=h.category, prob=h.prob, text=h.text_excerpt, color=color)))

    # Default annotated view over plain text
    annotated_html = inject_highlights(text, spans)

    # Counts + grouping by category
    counts: Dict[str, int] = {}
    hits_by_category: Dict[str, list] = {}
    for h in hits:
        counts[h.category] = counts.get(h.category, 0) + 1
        hits_by_category.setdefault(h.category, []).append(h)
    category_colors = {cat: category_color(cat) for cat in hits_by_category.keys()}

    summary_obj = Summary.query.filter_by(analysis_id=analysis.id).order_by(Summary.created_at.desc()).first()
    summary_text = summary_obj.output_text if summary_obj else ""

    is_pdf = os.path.splitext(contract.path.lower())[1] == ".pdf"
    # Compute page numbers for hits for PDF jump links
    hit_pages: Dict[int, int] = {}
    if is_pdf:
        try:
            import fitz  # PyMuPDF
            from bisect import bisect_right
            doc = fitz.open(contract.path)
            offsets = []
            cursor = 0
            for i, page in enumerate(doc):
                offsets.append(cursor)
                txt = page.get_text("text") or ""
                cursor += len(txt)
                if i < len(doc) - 1:
                    cursor += 2  # for the "\n\n" join used in parser
            doc.close()
            for h in hits:
                idx = max(0, int(h.start_char or 0))
                page_idx = max(0, bisect_right(offsets, idx) - 1)
                hit_pages[h.id] = page_idx + 1  # 1-based
        except Exception:
            hit_pages = {}

    return render_template(
        "analyze/result.html",
        analysis=analysis,
        contract=contract,
        counts=counts,
        total_hits=len(hits),
        annotated_html=annotated_html,
        raw_text=text,
        hits=hits,
        hits_by_category=hits_by_category,
        category_colors=category_colors,
        hit_index=hit_index,
        summary_text=summary_text,
        is_pdf=is_pdf,
        hit_pages=hit_pages,
    )


@bp.route("/<int:analysis_id>/export", methods=["POST"]) 
def export_report(analysis_id: int):
    analysis = Analysis.query.get_or_404(analysis_id)
    hits = Hit.query.filter_by(analysis_id=analysis_id).order_by(Hit.start_char.asc()).all()
    for idx, h in enumerate(hits, start=1):
        if not getattr(h, "color", None):
            setattr(h, "color", category_color(h.category))
    summary_obj = Summary.query.filter_by(analysis_id=analysis_id).order_by(Summary.created_at.desc()).first()
    summary_text = summary_obj.output_text if summary_obj else ""

    title = f"Risk Report - {analysis.contract.filename}"
    _settings = getattr(current_app, "settings", current_app.config.get("SETTINGS", {}))
    disclaimer = _settings.get("disclaimer", "")
    logo = _settings.get("logo_path") or None

    # HTML export
    html = render_report_html(title, [
        dict(category=h.category, prob=h.prob, text_excerpt=h.text_excerpt, color=getattr(h, "color", category_color(h.category)))
        for i, h in enumerate(hits)
    ], summary_text, disclaimer, logo)
    reports_dir = current_app.config["REPORT_FOLDER"]
    os.makedirs(reports_dir, exist_ok=True)
    base = os.path.splitext(os.path.basename(analysis.contract.filename))[0]
    html_path = os.path.join(reports_dir, f"{base}_report.html")
    save_html_report(html_path, html)

    # PDF export (simple)
    pdf_path = os.path.join(reports_dir, f"{base}_report.pdf")
    try:
        save_pdf_report(pdf_path, title, [
            dict(category=h.category, prob=h.prob, text_excerpt=h.text_excerpt, color=getattr(h, "color", category_color(h.category)))
            for i, h in enumerate(hits)
        ], summary_text, disclaimer)
    except Exception as e:
        flash(f"PDF export failed: {e}", "warning")

    flash("Report exported.", "success")
    return send_file(html_path, as_attachment=True)


@bp.route("/<int:analysis_id>/pdf")
def view_pdf(analysis_id: int):
    analysis = Analysis.query.get_or_404(analysis_id)
    contract = analysis.contract
    if not os.path.exists(contract.path) or not contract.path.lower().endswith(".pdf"):
        flash("Original file is not a PDF or not found.", "warning")
        return redirect(url_for("analyze.view_result", analysis_id=analysis_id))
    return send_file(contract.path, mimetype="application/pdf", as_attachment=False)


@bp.route("/<int:analysis_id>/pdf/highlighted")
def view_pdf_highlighted(analysis_id: int):
    analysis = Analysis.query.get_or_404(analysis_id)
    contract = analysis.contract
    if not os.path.exists(contract.path) or not contract.path.lower().endswith(".pdf"):
        flash("Original file is not a PDF or not found.", "warning")
        return redirect(url_for("analyze.view_result", analysis_id=analysis_id))

    base = os.path.splitext(os.path.basename(contract.filename))[0]
    out_path = os.path.join(current_app.config["REPORT_FOLDER"], f"{base}_highlighted.pdf")

    if not os.path.exists(out_path):
        # Prepare hits as dicts and generate highlights with PyMuPDF only
        hits = Hit.query.filter_by(analysis_id=analysis_id).order_by(Hit.start_char.asc()).all()
        for idx, h in enumerate(hits, start=1):
            if not getattr(h, "color", None):
                setattr(h, "color", category_color(h.category))
        try:
            hit_dicts = [dict(text_excerpt=h.text_excerpt, category=h.category, prob=h.prob, color=getattr(h, "color", category_color(h.category))) for i, h in enumerate(hits)]
            n_pym, _ = generate_highlighted_pdf(contract.path, hit_dicts, out_path)
            if n_pym == 0:
                flash("No highlights were added (texts not found in PDF).", "warning")
        except Exception as e:
            current_app.logger.exception("Failed to generate highlighted PDF")
            flash(f"Failed to generate highlighted PDF: {e}", "danger")
            try:
                os.makedirs(os.path.dirname(out_path), exist_ok=True)
                shutil.copyfile(contract.path, out_path)
            except Exception:
                current_app.logger.exception("Failed to copy original PDF for fallback")
                return send_file(contract.path, mimetype="application/pdf", as_attachment=False)

    return send_file(out_path, mimetype="application/pdf", as_attachment=False)


@bp.route("/<int:analysis_id>/pdf/viewer/<string:mode>")
def pdf_viewer(analysis_id: int, mode: str):
    analysis = Analysis.query.get_or_404(analysis_id)
    contract = analysis.contract
    if not os.path.exists(contract.path) or not contract.path.lower().endswith(".pdf"):
        flash("Original file is not a PDF or not found.", "warning")
        return redirect(url_for("analyze.view_result", analysis_id=analysis_id))
    if mode == "highlighted":
        file_url = url_for("analyze.view_pdf_highlighted", analysis_id=analysis_id)
        overlay = False
    else:
        file_url = url_for("analyze.view_pdf", analysis_id=analysis_id)
        overlay = True
    coords_url = url_for("analyze.pdf_coords", analysis_id=analysis_id, mode=mode)
    return render_template("analyze/pdf_viewer.html", file_url=file_url, coords_url=coords_url, overlay=overlay)


@bp.route("/<int:analysis_id>/pdf/coords/<string:mode>")
def pdf_coords(analysis_id: int, mode: str):
    analysis = Analysis.query.get_or_404(analysis_id)
    contract = analysis.contract
    if not os.path.exists(contract.path) or not contract.path.lower().endswith(".pdf"):
        return jsonify(dict(ok=False, error="Not a PDF")), 400
    # Select file to analyze (original is fine; coords generally same)
    src_path = contract.path
    # Prepare hits with IDs and text excerpts
    hits = Hit.query.filter_by(analysis_id=analysis_id).order_by(Hit.start_char.asc()).all()
    for idx, h in enumerate(hits, start=1):
        if not getattr(h, "color", None):
            setattr(h, "color", category_color(h.category))
    hit_dicts = [dict(id=h.id, text_excerpt=h.text_excerpt, category=h.category, prob=h.prob, color=getattr(h, "color", category_color(h.category))) for i, h in enumerate(hits)]
    try:
        rects = compute_hit_rects(src_path, hit_dicts)
        # Fallback page mapping for jump when no rects are found
        pages_by_hit = {}
        try:
            import fitz
            from bisect import bisect_right
            doc = fitz.open(src_path)
            offsets = []
            page_heights_points = {}
            cursor = 0
            for i, page in enumerate(doc):
                offsets.append(cursor)
                txt = page.get_text("text") or ""
                cursor += len(txt)
                if i < len(doc) - 1:
                    cursor += 2  # for the "\n\n" join used in parser
                # record page height in PDF points for accurate y-flip
                try:
                    page_heights_points[str(i + 1)] = float(page.rect.height)
                except Exception:
                    pass
            for h in hits:
                idx = max(0, int(h.start_char or 0))
                page_idx = max(0, bisect_right(offsets, idx) - 1)
                pages_by_hit[str(h.id)] = page_idx + 1
            doc.close()
        except Exception:
            pages_by_hit = {}
            page_heights_points = {}
        return jsonify(dict(ok=True, rects=rects, pages_by_hit=pages_by_hit, page_heights_points=page_heights_points, hits=hit_dicts))
    except Exception as e:
        return jsonify(dict(ok=False, error=str(e))), 500


@bp.route("/<int:analysis_id>/explain/<int:hit_id>", methods=["POST"]) 
def explain_hit(analysis_id: int, hit_id: int):
    config = current_app.config
    settings = getattr(current_app, "settings", config.get("SETTINGS", {}))
    h = Hit.query.filter_by(id=hit_id, analysis_id=analysis_id).first_or_404()
    text = h.text_excerpt or ""
    if not settings.get("enable_gemini", False):
        return jsonify({"ok": False, "error": "Gemini disabled in settings."}), 400
    explanation = generate_clause_explanation(h.category, text, settings.get("gemini_model", "gemini-2.0-flash"))
    return jsonify({"ok": True, "explanation": explanation})


