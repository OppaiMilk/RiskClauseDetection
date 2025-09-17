import os
from typing import Dict, List


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


def generate_overall_summary(hits_by_category: Dict[str, List[str]], model_name: str = "gemini-2.0-flash") -> str:
    genai = _get_client()
    if genai is None:
        return "Gemini API key not configured. Set GEMINI_API_KEY to enable summaries."

    prompt_lines = [
        "You are a legal assistant. Given detected contract clauses grouped by category, write a concise 4-6 bullet risk summary in plain English for a Malaysian context. Avoid legalese. Keep each bullet <= 20 words. Categories: Payment Terms, Liability & Exclusions, Termination, Intellectual Property, Confidentiality.",
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
        return "Gemini API key not configured."

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