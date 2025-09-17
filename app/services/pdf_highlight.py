import os
from typing import List, Dict, Tuple
import re


CATEGORY_STYLE_MAP: Dict[str, Dict[str, str]] = {
    "payment terms": {"fill": "#E3F2FD", "stroke": "#1565C0"},
    "liability & exclusions": {"fill": "#FCE4EC", "stroke": "#AD1457"},
    "termination": {"fill": "#E8F5E9", "stroke": "#2E7D32"},
    "intellectual property": {"fill": "#FFF3E0", "stroke": "#EF6C00"},
    "confidentiality": {"fill": "#EDE7F6", "stroke": "#5E35B1"},
}
DEFAULT_STYLE = {"fill": "#FFF9C4", "stroke": "#F9A825"}


def _category_key(category: str) -> str:
    return (category or "").strip().lower()


def _style_for_category(category: str) -> Dict[str, str]:
    base = CATEGORY_STYLE_MAP.get(_category_key(category), DEFAULT_STYLE)
    # return a copy so we never mutate the constant dictionaries
    return dict(base)


def _hex_to_rgb(color: str) -> Tuple[int, int, int]:
    value = color.lstrip("#")
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    r = int(value[0:2], 16)
    g = int(value[2:4], 16)
    b = int(value[4:6], 16)
    return r, g, b


def _hex_to_rgb01(color: str) -> Tuple[float, float, float]:
    r, g, b = _hex_to_rgb(color)
    return (r / 255.0, g / 255.0, b / 255.0)




def _normalize_hex(color: str) -> str:
    if not color:
        return ""
    c = color.strip()
    if not c.startswith("#"):
        c = "#" + c
    return c


def _build_search_phrases(text: str, max_len: int = 90) -> List[str]:
    """Return a few short phrases to look for in the PDF.
    Uses beginning and middle snippets to improve chances of a match.
    """
    if not text:
        return []
    s = " ".join(text.split())  # normalize whitespace
    if len(s) <= max_len:
        return [s]
    head = s[:max_len]
    mid_start = max(0, (len(s) // 2) - (max_len // 2))
    mid = s[mid_start: mid_start + max_len]
    return [head, mid]


def _search_rects_case_insensitive(page, phrase: str):
    """Find rectangles for phrase on a page, case-insensitively.
    Strategy: find lowercase match in page text, then search again with
    the exact-cased substring to obtain rectangles.
    """
    text = page.get_text("text") or ""
    rects = []
    for m in re.finditer(re.escape(phrase), text, flags=re.IGNORECASE):
        found = text[m.start():m.end()]
        try:
            rects.extend(page.search_for(found) or [])
        except TypeError:
            rects.extend(page.search_for(found))
    return rects


def _norm_token(s: str) -> str:
    s = s.lower()
    # remove punctuation and join hyphenated tokens
    s = re.sub(r"[\-\u00AD]", "", s)  # hyphen and soft hyphen
    s = re.sub(r"[^a-z0-9]+", "", s)
    return s


def _tokenize_phrase(phrase: str) -> List[str]:
    # normalize whitespace and split, then normalize tokens
    parts = phrase.split()
    toks = [_norm_token(p) for p in parts]
    return [t for t in toks if t]


def _search_rects_by_words(page, phrase: str) -> List["fitz.Rect"]:
    import fitz  # type: ignore
    toks = _tokenize_phrase(phrase)
    if not toks:
        return []
    words = page.get_text("words") or []
    seq = []
    rects = []
    for w in words:
        try:
            x0, y0, x1, y1, text = float(w[0]), float(w[1]), float(w[2]), float(w[3]), str(w[4])
        except Exception:
            # Fallback if tuple shape differs
            if len(w) >= 5:
                x0, y0, x1, y1, text = float(w[0]), float(w[1]), float(w[2]), float(w[3]), str(w[4])
            else:
                continue
        t = _norm_token(text)
        if not t:
            continue
        seq.append((t, fitz.Rect(x0, y0, x1, y1)))
    n = len(toks)
    if n == 0 or len(seq) < n:
        return []

    def group_by_line(word_rects):
        lines = []
        eps = 3.0  # tolerance in points for baseline grouping
        for _, rr in word_rects:
            y = (rr.y0 + rr.y1) / 2.0
            placed = False
            for line in lines:
                ly = line[0]
                if abs(y - ly) <= eps:
                    line[1].append(rr)
                    placed = True
                    break
            if not placed:
                lines.append([y, [rr]])
        # build tight rect for each line
        out = []
        for _, rs in lines:
            acc = rs[0]
            for rr in rs[1:]:
                acc |= rr
            out.append(acc)
        return out

    for i in range(0, len(seq) - n + 1):
        window = seq[i:i + n]
        ok = True
        for j in range(n):
            ptok = window[j][0]
            qtok = toks[j]
            if j == 0 or j == n - 1:
                if not ptok.startswith(qtok):
                    ok = False
                    break
            else:
                if ptok != qtok:
                    ok = False
                    break
        if ok:
            # return per-line rectangles for prettier highlights
            rects.extend(group_by_line(window))
    return rects


def _css_class(category: str) -> str:
    if not category:
        return "other"
    slug = re.sub(r"[^a-z0-9]+", "-", category.lower()).strip("-")
    return slug or "other"


def generate_highlighted_pdf(src_pdf_path: str, hits: List[Dict], out_path: str) -> Tuple[int, str]:
    """Create a copy of the original PDF with highlight annotations where hit excerpts appear.

    - src_pdf_path: path to the original PDF
    - hits: list of dicts with at least {'text_excerpt': str}
    - out_path: destination path for highlighted PDF

    Returns: (num_highlights, out_path)
    """
    import fitz  # PyMuPDF

    if not os.path.exists(src_pdf_path):
        raise FileNotFoundError(src_pdf_path)

    doc = fitz.open(src_pdf_path)
    try:
        total = 0
        for page in doc:
            for h in hits:
                text_excerpt = h.get("text_excerpt") or ""
                custom_color = _normalize_hex(h.get("color") or "")
                if custom_color:
                    fill_hex = custom_color
                    stroke_hex = custom_color
                else:
                    style = _style_for_category(h.get("category"))
                    fill_hex = _normalize_hex(style["fill"])
                    stroke_hex = _normalize_hex(style.get("stroke", style["fill"]))
                fill_rgb = _hex_to_rgb01(fill_hex)
                stroke_rgb = _hex_to_rgb01(stroke_hex)
                for phrase in _build_search_phrases(text_excerpt, max_len=90):
                    if not phrase:
                        continue
                    rects = _search_rects_by_words(page, phrase)
                    if not rects:
                        rects = _search_rects_case_insensitive(page, phrase)
                    for r in rects:
                        annot = page.add_highlight_annot(r)
                        if annot is None:
                            continue
                        try:
                            # Highlights ignore fill color, so only stroke controls appearance.
                            annot.set_colors(stroke=stroke_rgb)
                            annot.set_opacity(0.75)
                            annot.set_info(title=h.get("category"), content=f"Confidence {h.get('prob', 0.0):.2f}")
                            annot.update()
                        except Exception:
                            pass
                        total += 1
        dest_dir = os.path.dirname(out_path)
        if dest_dir:
            os.makedirs(dest_dir, exist_ok=True)
        doc.save(out_path, incremental=False, deflate=True)
        return total, out_path
    finally:
        doc.close()


def compute_hit_rects(src_pdf_path: str, hits: List[Dict]) -> List[Dict]:
    """Compute rectangles for each hit phrase.
    Returns list of dicts: {hit_id, page, x0, y0, x1, y1, category, css_class, fill_color, stroke_color}
    """
    import fitz  # PyMuPDF
    if not os.path.exists(src_pdf_path):
        raise FileNotFoundError(src_pdf_path)
    doc = fitz.open(src_pdf_path)
    try:
        out: List[Dict] = []
        for page_index, page in enumerate(doc):
            for h in hits:
                text_excerpt = h.get("text_excerpt") or ""
                hit_id = h.get("id")
                category = h.get("category")
                custom_color = _normalize_hex(h.get("color") or "")
                if custom_color:
                    fill_hex = custom_color
                    stroke_hex = custom_color
                else:
                    style = _style_for_category(category)
                    fill_hex = _normalize_hex(style["fill"])
                    stroke_hex = _normalize_hex(style.get("stroke", fill_hex))
                for phrase in _build_search_phrases(text_excerpt, max_len=90):
                    if not phrase:
                        continue
                    # Prefer word-based matching for accurate boxes
                    rects = _search_rects_by_words(page, phrase)
                    if not rects:
                        rects = _search_rects_case_insensitive(page, phrase)
                    for r in rects:
                        out.append({
                            "hit_id": hit_id,
                            "page": page_index + 1,
                            "x0": float(r.x0),
                            "y0": float(r.y0),
                            "x1": float(r.x1),
                            "y1": float(r.y1),
                            "category": category,
                            "css_class": _css_class(category),
                            "fill_color": fill_hex,
                            "stroke_color": stroke_hex,
                            "prob": float(h.get("prob", 0.0)),
                        })
        return out
    finally:
        doc.close()

