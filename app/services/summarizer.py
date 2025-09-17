import os
from typing import Dict, List
import google.generativeai as genai


def _get_client():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None
    import google.generativeai as genai
    genai.configure(api_key=api_key)
    return genai


def _safe_text(resp) -> str:
    if resp is None:
        return ""
    text = getattr(resp, "text", None)
    if text:
        return text
    candidates = getattr(resp, "candidates", None)
    if not candidates:
        return ""
    for cand in candidates:
        content = getattr(cand, "content", None)
        if not content:
            continue
        parts = getattr(content, "parts", None)
        if not parts:
            continue
        texts = [getattr(part, "text", "") for part in parts if getattr(part, "text", "")]
        if texts:
            return "\n".join(texts)
    return ""



def _fallback_summary(hits_by_category: Dict[str, List[str]]) -> str:
    total_hits = sum(len(v or []) for v in hits_by_category.values())
    if total_hits == 0:
        return ("**Quick risk snapshot (no AI)**\n\n- **Overview** - No risky clauses detected by the classifier. Review key terms manually to confirm the contract still fits your needs.")

    sorted_items = sorted(((cat or 'Uncategorised', len(texts or [])) for cat, texts in hits_by_category.items()), key=lambda x: x[1], reverse=True)
    lines = ["**Quick risk snapshot (no AI)**\n"]
    for cat, count in sorted_items[:6]:
        plural = 's' if count != 1 else ''
        lines.append(f"- **{cat}** - {count} clause{plural} flagged; make sure obligations stay workable.")
    return "\n".join(lines)





def generate_overall_summary(hits_by_category: Dict[str, List[str]], model_name: str = "gemini-2.0-flash") -> str:
    genai = _get_client()
    if genai is None:
        return _fallback_summary(hits_by_category)

    prompt_lines = [
        "You are a legal assistant. Produce a polished Markdown risk summary for a Malaysian business reader.",
        "Formatting rules:",
        "- Begin with a single bold overview line summarising overall risk.",
        "- Follow with 4-6 bullet points.",
        "- Each bullet starts with a bold category name, an en dash, then 1-2 short sentences in plain English.",
        "- Keep wording friendly, avoid legal jargon or disclaimers.",
        "",
        "Detected clauses:",
    ]
    for cat, texts in hits_by_category.items():
        if not texts:
            continue
        joined = " | ".join(t[:500] for t in texts[:5])
        prompt_lines.append(f"- {cat}: {joined}")
    content = "\n".join(prompt_lines).strip()

    try:
        model = genai.GenerativeModel(model_name)
        resp = model.generate_content(content)
        text = _safe_text(resp).strip()
        return text or "(No summary returned)"
    except Exception as e:
        return f"Gemini summarization error: {e}"


def generate_clause_explanation(category: str, clause_text: str, model_name: str = "gemini-2.0-flash") -> str:
    genai = _get_client()
    if genai is None:
        snippet = (clause_text or '').strip().replace('\n', ' ')[:220]
        note = 'Gemini disabled; review manually.'
        if snippet:
            return f"{note} Key excerpt: {snippet}"
        return note

    instruction = (
        f"Explain in 2-3 sentences why this {category} clause may pose risk in a Malaysian contract. "
        "Use plain English. Avoid legal disclaimers."
    )
    content = f"{instruction}\n\nClause:\n{(clause_text or '')[:1200]}"

    try:
        model = genai.GenerativeModel(model_name)
        resp = model.generate_content(content)
        text = _safe_text(resp).strip()
        return text or "(No explanation returned)"
    except Exception as e:
        return f"Gemini explanation error: {e}"
