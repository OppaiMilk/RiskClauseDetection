from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List, Dict, Any, Tuple, Optional

import math
import regex as re
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification


DEFAULT_LABELS = [
    "Payment Terms",
    "Liability & Exclusions",
    "Termination",
    "Intellectual Property",
    "Confidentiality",
    "Other",
]


CATEGORY_COLOR_MAP: Dict[str, str] = {
    "payment terms": "#E3F2FD",
    "liability & exclusions": "#FCE4EC",
    "termination": "#E8F5E9",
    "intellectual property": "#FFF3E0",
    "confidentiality": "#EDE7F6",
    "other": "#FFF9C4",
}
DEFAULT_HIT_COLOR = "#FFF9C4"







def _parse_model_spec(spec: str) -> Tuple[str, Optional[str], Optional[str]]:
    if not spec:
        return "", None, None
    base = str(spec).strip()
    revision: Optional[str] = None
    subfolder: Optional[str] = None
    if "::" in base:
        base, sub = base.split("::", 1)
        subfolder = sub.strip() or None
    if "@" in base:
        base, rev = base.split("@", 1)
        revision = rev.strip() or None
    return base.strip(), revision, subfolder


def model_display_name(spec: str) -> str:
    base, _, sub = _parse_model_spec(spec or "")
    if not base:
        return ""
    norm = base.replace("\\", "/").rstrip("/")
    name = norm.split("/")[-1] if norm else base
    if sub:
        return f"{name}/{sub}"
    return name

def _category_key(category: str) -> str:
    return (category or "").strip().lower()


def category_color(category: str) -> str:
    return CATEGORY_COLOR_MAP.get(_category_key(category), DEFAULT_HIT_COLOR)


@dataclass
class Segment:
    text: str
    start: int
    end: int
    page_no: int | None = None


@dataclass
class ClassifiedSpan:
    start: int
    end: int
    page_no: int | None
    category: str
    prob: float
    text: str
    color: Optional[str] | None = None


class RiskClassifier:
    _instance = None

    def __init__(self, model_name_or_path: str):
        if not model_name_or_path:
            raise ValueError(
                "Model name or path is missing. Set 'model_name_or_path' in app/settings.json or provide a valid path."
            )
        base, revision, subfolder = _parse_model_spec(model_name_or_path)
        if not base:
            raise ValueError(f"Unable to determine model identifier from specification: {model_name_or_path}")
        load_kwargs: Dict[str, Any] = {}
        if revision:
            load_kwargs["revision"] = revision
        if subfolder:
            load_kwargs["subfolder"] = subfolder
        self.model_name_or_path = model_name_or_path
        self._resolved_model_path = base
        self._revision = revision
        self._subfolder = subfolder
        self.tokenizer = AutoTokenizer.from_pretrained(base, **load_kwargs)
        self.model = AutoModelForSequenceClassification.from_pretrained(base, **load_kwargs)
        self.model.eval()
        self.id2label = getattr(self.model.config, "id2label", None)
        if not self.id2label or len(self.id2label) == 0:
            # fallback to default mapping
            self.id2label = {i: lab for i, lab in enumerate(DEFAULT_LABELS)}

    @classmethod
    def get(cls, model_name_or_path: str) -> "RiskClassifier":
        if cls._instance is None or cls._instance.model_name_or_path != model_name_or_path:
            cls._instance = RiskClassifier(model_name_or_path)
        return cls._instance

    def predict(self, texts: List[str]) -> List[Tuple[str, float]]:
        # returns (label, prob)
        if not texts:
            return []
        enc = self.tokenizer(texts, padding=True, truncation=True, max_length=512, return_tensors="pt")
        with torch.no_grad():
            logits = self.model(**enc).logits
            probs = torch.softmax(logits, dim=-1).cpu().numpy()

        results: List[Tuple[str, float]] = []
        for p in probs:
            idx = int(p.argmax())
            label = self.id2label.get(idx, "Other")
            results.append((label, float(p[idx])))
        return results


def split_into_paragraphs(text: str) -> List[Segment]:
    parts = re.split(r"\n\s*\n+", text)
    segments: List[Segment] = []
    cursor = 0
    for part in parts:
        raw = part.strip()
        if not raw:
            continue
        normalized = re.sub(r"\s+", " ", raw)
        if not normalized:
            continue
        if len(normalized) < 80:
            idx = text.find(raw, cursor)
            if idx != -1:
                cursor = idx + len(raw)
            continue
        if re.fullmatch(r"page\s*\d+(\s*of\s*\d+)?", normalized, flags=re.IGNORECASE):
            idx = text.find(raw, cursor)
            if idx != -1:
                cursor = idx + len(raw)
            continue
        idx = text.find(raw, cursor)
        if idx == -1:
            idx = cursor
        start = idx
        end = idx + len(raw)
        segments.append(Segment(text=raw, start=start, end=end, page_no=None))
        cursor = end
    return segments


def chunk_long_segment(seg: Segment, tokenizer, max_length_tokens=400, stride_tokens=120) -> List[Segment]:
    tokens = tokenizer(seg.text, add_special_tokens=False, return_offsets_mapping=True)
    offsets = tokens["offset_mapping"]
    # Build chunks by token spans
    spans = []
    i = 0
    n = len(offsets)
    while i < n:
        j = min(i + max_length_tokens, n)
        tok_start = offsets[i][0]
        tok_end = offsets[j - 1][1]
        spans.append((tok_start, tok_end))
        if j == n:
            break
        i = max(0, j - stride_tokens)
    chunks: List[Segment] = []
    for (a, b) in spans:
        start = seg.start + a
        end = seg.start + b
        text_span = seg.text[a:b]
        chunks.append(Segment(text=text_span, start=start, end=end, page_no=seg.page_no))
    return chunks


def classify_text(
    full_text: str,
    model_name_or_path: str,
    threshold: float = 0.6,
    merge_window_chars: int = 80,
) -> List[ClassifiedSpan]:
    clf = RiskClassifier.get(model_name_or_path)
    segments = split_into_paragraphs(full_text)

    # Expand long segments into sliding windows
    expanded: List[Segment] = []
    for seg in segments:
        if len(seg.text.split()) > 180:
            expanded.extend(chunk_long_segment(seg, clf.tokenizer))
        else:
            expanded.append(seg)

    preds = clf.predict([s.text for s in expanded])
    spans: List[ClassifiedSpan] = []
    for seg, (label, prob) in zip(expanded, preds):
        if prob < threshold:
            label = "Other"
        if label == "Other":
            continue
        spans.append(
            ClassifiedSpan(
                start=seg.start,
                end=seg.end,
                page_no=seg.page_no,
                category=label,
                prob=prob,
                text=seg.text.strip(),
            )
        )

    # Merge nearby spans of the same category
    spans.sort(key=lambda s: (s.start, s.end))
    merged: List[ClassifiedSpan] = []
    for sp in spans:
        if not merged:
            merged.append(sp)
            continue
        last = merged[-1]
        if sp.category == last.category and sp.start - last.end <= merge_window_chars:
            # merge
            new_text = (full_text[last.start:sp.end]).strip()
            merged[-1] = ClassifiedSpan(
                start=last.start,
                end=sp.end,
                page_no=sp.page_no,
                category=sp.category,
                prob=max(last.prob, sp.prob),
                text=new_text,
            )
        else:
            merged.append(sp)

    return merged


def inject_highlights(full_text: str, spans: List[ClassifiedSpan]) -> str:
    # Build HTML with span anchors around classified regions
    if not spans:
        return f"<pre class=\"preview-text\">{escape_html(full_text)}</pre>"
    spans = sorted(spans, key=lambda s: s.start)
    html_parts = []
    cursor = 0
    for idx, sp in enumerate(spans):
        if sp.start > cursor:
            html_parts.append(escape_html(full_text[cursor:sp.start]))
        frag = escape_html(full_text[sp.start:sp.end])
        anchor = f"hit-{idx+1}"
        color = getattr(sp, "color", None) or category_color(sp.category)
        style_attr = f" style=\"background-color:{color};\"" if color else ""
        html_parts.append(
            f"<span id=\"{anchor}\" class=\"highlight category-{css_class(sp.category)}\" data-color=\"{color}\" title=\"{sp.category} - Confidence {sp.prob:.2f}\"{style_attr}>{frag}</span>"
        )
        cursor = sp.end
    if cursor < len(full_text):
        html_parts.append(escape_html(full_text[cursor:]))

    return f"<pre class=\"preview-text\">{''.join(html_parts)}</pre>"


def css_class(category: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", category.lower())


def escape_html(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


