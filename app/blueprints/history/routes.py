from flask import render_template, redirect, url_for, flash
from . import bp
from ... import db
from ...models import Contract, Analysis, Hit


@bp.route("/")
def list_history():
    analyses = (
        db.session.query(Analysis)
        .order_by(Analysis.finished_at.desc())
        .all()
    )
    # Top category for each analysis
    top_categories = {}
    for a in analyses:
        counts = {}
        for h in a.hits:
            counts[h.category] = counts.get(h.category, 0) + 1
        top = max(counts.items(), key=lambda x: x[1])[0] if counts else "-"
        top_categories[a.id] = top
    return render_template("history/list.html", analyses=analyses, top_categories=top_categories)


@bp.route("/<int:analysis_id>")
def view_analysis(analysis_id: int):
    return redirect(url_for("analyze.view_result", analysis_id=analysis_id))


@bp.route("/<int:analysis_id>/reanalyze", methods=["POST"]) 
def reanalyze(analysis_id: int):
    a = Analysis.query.get_or_404(analysis_id)
    # Re-run using the same contract file
    from ...services.parser import parse_document
    from ...services.inference import classify_text, model_display_name
    from ...models import Hit, Summary
    from flask import current_app
    import os

    contract = a.contract
    if not os.path.exists(contract.path):
        flash("Original file not found on disk.", "danger")
        return redirect(url_for("history.list_history"))

    text, _ = parse_document(contract.path)
    settings = current_app.settings
    spans = classify_text(
        text,
        settings.get("model_name_or_path"),
        threshold=float(settings.get("threshold", 0.6)),
        merge_window_chars=int(settings.get("merge_window_chars", 80)),
    )

    new_a = Analysis(
        contract_id=contract.id,
        model_name=model_display_name(settings.get("model_name_or_path")),
        model_version="1.0",
        total_hits=len(spans),
    )
    db.session.add(new_a)
    db.session.flush()

    for sp in spans:
        db.session.add(Hit(
            analysis_id=new_a.id,
            category=sp.category,
            prob=sp.prob,
            page_no=sp.page_no or 0,
            start_char=sp.start,
            end_char=sp.end,
            text_excerpt=sp.text,
            ambiguous=sp.prob < (float(settings.get("threshold", 0.6)) + 0.05),
        ))
    db.session.commit()

    flash("Re-analysis completed.", "success")
    return redirect(url_for("analyze.view_result", analysis_id=new_a.id))


@bp.route("/<int:analysis_id>/delete", methods=["POST"]) 
def delete_analysis(analysis_id: int):
    a = Analysis.query.get_or_404(analysis_id)
    db.session.delete(a)
    db.session.commit()
    flash("Analysis deleted.", "success")
    return redirect(url_for("history.list_history"))


