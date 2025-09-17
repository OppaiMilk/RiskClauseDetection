import os
from typing import List, Dict


def render_report_html(title: str, hits: List[dict], summary_text: str, disclaimer: str, logo_path: str | None = None) -> str:
    style = """
    <style>
      body { font-family: Arial, sans-serif; margin: 24px; }
      .header { display: flex; align-items: center; gap: 16px; }
      .logo { height: 48px; }
      .hit { border: 1px solid #ddd; padding: 8px 12px; margin: 8px 0; border-radius: 6px; }
      .cat { font-weight: bold; }
      .meta { color: #666; font-size: 12px; }
      .summary { background: #f9fafb; padding: 12px; border-radius: 6px; }
      .footer { margin-top: 24px; color: #777; font-size: 12px; }
      .pill { display:inline-block; padding:2px 8px; border-radius:999px; font-size:12px; color:#1f2933; }
    </style>
    """
    logo_html = f'<img class="logo" src="{logo_path}" />' if logo_path else ""
    html = ["<html><head><meta charset='utf-8'>", style, "</head><body>"]
    html.append(f"<div class='header'>{logo_html}<h2>{title}</h2></div>")
    if summary_text:
        html.append(f"<h3>Summary</h3><div class='summary'><pre style='white-space:pre-wrap'>{summary_text}</pre></div>")
    html.append("<h3>Detected Clauses</h3>")
    for h in hits:
        cat = h.get("category", "")
        prob = h.get("prob", 0.0)
        text = h.get("text_excerpt", "")
        color = (h.get("color") or "").strip() or '#ddd'
        pill_style = f" style=\"background:{color}\""
        html.append(
            f"<div class='hit'><div class='cat'><span class='pill'{pill_style}>{cat}</span> &nbsp; <span class='meta'>Confidence {prob:.2f}</span></div>"
            f"<div><pre style='white-space:pre-wrap'>{escape_html(text)}</pre></div></div>"
        )
    if disclaimer:
        html.append(f"<div class='footer'>{escape_html(disclaimer)}</div>")
    html.append("</body></html>")
    return "".join(html)


def save_html_report(path: str, html: str):
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)


def save_pdf_report(path: str, title: str, hits: List[dict], summary_text: str, disclaimer: str):
    # Minimal PDF using reportlab; text only (no fancy layout)
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import cm
    from reportlab.lib.utils import simpleSplit
    width, height = A4
    c = canvas.Canvas(path, pagesize=A4)
    x_margin = 2 * cm
    y = height - 2 * cm

    def draw_wrapped(text: str, font="Helvetica", size=10, max_width=width - 4 * cm, leading=14):
        nonlocal y
        c.setFont(font, size)
        lines = simpleSplit(text, font, size, max_width)
        for line in lines:
            if y < 2 * cm:
                c.showPage(); y = height - 2 * cm
                c.setFont(font, size)
            c.drawString(x_margin, y, line)
            y -= leading

    c.setFont("Helvetica-Bold", 14)
    c.drawString(x_margin, y, title)
    y -= 20

    if summary_text:
        c.setFont("Helvetica-Bold", 12)
        c.drawString(x_margin, y, "Summary")
        y -= 16
        draw_wrapped(summary_text, size=10)
        y -= 6

    c.setFont("Helvetica-Bold", 12)
    c.drawString(x_margin, y, "Detected Clauses")
    y -= 16

    for h in hits:
        head = f"[{h.get('category','')}] Confidence {h.get('prob',0.0):.2f}"
        c.setFont("Helvetica-Bold", 10)
        c.drawString(x_margin, y, head)
        y -= 14
        draw_wrapped(h.get("text_excerpt", ""), size=9, leading=12)
        y -= 8

    if disclaimer:
        y -= 10
        c.setFont("Helvetica", 8)
        draw_wrapped("Disclaimer: " + disclaimer, size=8, leading=10)

    c.save()


def escape_html(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )

