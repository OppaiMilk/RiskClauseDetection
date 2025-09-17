import os
import hashlib
from typing import Tuple


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()


def _parse_pdf(path: str) -> Tuple[str, int]:
    import fitz  # PyMuPDF
    texts: list[str] = []
    with fitz.open(path) as doc:
        page_count = len(doc)
        for page in doc:
            texts.append(page.get_text("text") or "")
    full = "\n\n".join(texts)
    return full, page_count


def _parse_docx(path: str) -> Tuple[str, int]:
    from docx import Document
    doc = Document(path)
    paragraphs = [p.text for p in doc.paragraphs]
    return "\n\n".join(paragraphs), 0


def _parse_txt(path: str) -> Tuple[str, int]:
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        return f.read(), 0


def parse_document(path: str) -> Tuple[str, int]:
    _, ext = os.path.splitext(path.lower())
    if ext in [".pdf"]:
        return _parse_pdf(path)
    if ext in [".docx", ".doc"]:
        # Note: .doc is not directly supported; user should convert to .docx
        return _parse_docx(path)
    return _parse_txt(path)


