# Contract Risk Detection 每 Code Tour

Below is a walkthrough of the major modules that power the contract clause risk assistant. Use this as a map when you need to modify behaviour, swap models, or wire the app into another environment.

---

## 1. High-Level Flow

1. **Upload** 每 User sends a PDF/DOCX via `app/blueprints/analyze/routes.py::run_analysis`.
2. **Parse** 每 `app/services/parser.py` extracts plain text + metadata (page counts).
3. **Classify** 每 `app/services/inference.py` loads `StudySeur/LegalBERT-finetuning-Malaysia` (or any HF model) and returns risky spans with probabilities.
4. **Persist** 每 `Contract`, `Analysis`, `Hit`, and optional `Summary` rows are written via SQLAlchemy.
5. **Render** 每 Results view (`app/templates/analyze/result.html`) shows category intros, clause risk levels, PDF highlights, Gemini explanations, etc.
6. **History / Export** 每 Users can re-run, delete, or export reports. Deletes also remove the source upload and generated exports when no other analyses reference them.

---

## 2. Configuration & Startup

### `app/__init__.py`
- Creates the Flask app, configures SQLAlchemy, and reads defaults from `app/settings.json` (merged with runtime overrides stored in the DB).
- Ensures `uploads/` and `reports/` directories exist.
- Registers blueprints: `analyze`, `history`, `main`, `settings`.
- Injects helpers/settings (`current_time`, `settings`) into Jinja templates.

### Environment Variables
Defined in `.env.example`:
- `MODEL_NAME_OR_PATH` points at the public Hugging Face repo `StudySeur/LegalBERT-finetuning-Malaysia` by default.
- `GEMINI_API_KEY` unlocks AI explanations & summaries.
- Other Flask settings (`SECRET_KEY`, `FLASK_RUN_PORT`, etc.) follow standard conventions.

---

## 3. Data Models (`app/models.py`)
- **Contract**: represents an uploaded file; cascade deletes will remove linked analyses when the contract is deleted.
- **Analysis**: one model run over a contract; stores metadata (model name, finished timestamp, total hits).
- **Hit**: an individual detected clause with category, probability, excerpt, offsets, page.
- **Summary**: optional Gemini generated text tied to an analysis.

---

## 4. Blueprints & Views

### Analyze (`app/blueprints/analyze/routes.py`)
- `/analyze/` (**GET**) 每 upload form.
- `/analyze/run` (**POST**) 每 validates upload, saves file, calls parser + classifier, writes DB rows.
- `/analyze/<analysis_id>` 每 composes the results page:
  - Builds highlighted HTML preview (`inject_highlights`), PDF jump support, category counts.
  - Adds plain-language category intros (`CATEGORY_TIPS`) and per-hit risk labels via `risk_level_summary`.
  - Loads Gemini summary when enabled.
- `/export` endpoints 每 produces HTML/PDF reports (`app/services/report.py`).
- `/pdf/*` endpoints 每 generate or stream highlighted PDFs (`app/services/pdf_highlight.py`).
- `/explain/<hit_id>` 每 on-demand Gemini clause explanation.

### History (`app/blueprints/history/routes.py`)
- `/history/` 每 lists analyses, showing top category per run.
- `/history/<id>` 每 shortcut to the result view.
- `/history/<id>/reanalyze` 每 reprocesses the same contract with current settings/model.
- `/history/<id>/delete` 每 removes the analysis **and** cleans up:
  - If it was the last analysis for that contract, deletes the contract row, uploaded file, and any generated reports (HTML/PDF/highlighted PDF).
  - Uses guarded `safe_remove` helper with logging.

### Main (`app/blueprints/main/routes.py`)
- Landing page, quick shortcuts to upload/history/settings.

### Settings (`app/blueprints/settings/routes.py`)
- UI to change runtime settings (thresholds, model path, Gemini toggle, branding assets).
- Persists values in DB-backed settings table; merge logic lives in `app/__init__.py`.

---

## 5. Service Layer

| Module | Purpose |
| ------ | ------- |
| `app/services/inference.py` | Loads Hugging Face classifier once (`RiskClassifier` singleton); splits text, adds sliding window for long segments, merges contiguous spans of the same category, decorates hits with colors. |
| `app/services/parser.py` | Handles PDF (PyMuPDF), DOCX (`python-docx`), and plaintext ingestion. Computes SHA-256 for deduplication. |
| `app/services/pdf_highlight.py` | Finds clause text inside the PDF, applies highlight annotations, and exports highlighted copies. Also returns hit rectangles for in-browser overlay/jump support. |
| `app/services/report.py` | Renders HTML report snippets and generates simple PDF exports via ReportLab. |
| `app/services/summarizer.py` | Wraps Google Gemini: produces overall summaries and clause explanations when `GEMINI_API_KEY` is present. |

---

## 6. Templates & Front-End Behaviour

- `app/templates/analyze/result.html`
  - Accordion grouped by category with `category_intros` (plain-language explanations), confidence badges, and risk labels (`High/Medium/Low`).
  - Buttons to jump to highlight (text preview or PDF) and trigger Gemini explanations.
  - Includes JS helpers for synchronised scrolling/JIT loading of PDF iframes.
- `app/templates/analyze/upload.html`
  - Styled drag/drop uploader with progress feedback.
- `app/templates/history/list.html`
  - History table, re-analyze/delete actions.
- `app/templates/settings/*`
  - Forms for thresholds, model path, Gemini toggle, branding.

Static assets (`app/static/`) contain CSS/JS for visual polish.

---

## 7. Generated Assets

- `uploads/` 每 raw contract uploads (ignored by Git). Automatically deleted when their final analysis is removed.
- `reports/` 每 exported HTML/PDF/highlighted PDFs (also Git-ignored and cleaned up with deletions).

---

## 8. Extending the Project

- **New Categories**: update `CATEGORY_TIPS` (in analyze blueprint) and optionally tweak colors in `CATEGORY_COLOR_MAP` / `CATEGORY_STYLE_MAP`.
- **Different NLP Model**: set `MODEL_NAME_OR_PATH` to another Hugging Face repo or local path; the inference service handles revisions/subfolders.
- **Extra Outputs**: extend `app/services/report.py` or add new blueprints for integrations (e.g., webhook callbacks).
- **Testing**: add pytest suites covering parser, inference pipeline, and blueprint routes (`pytest` already listed in requirements).

---

This doc should give you (and future collaborators) enough context to navigate the codebase quickly. For deeper implementation details, open the referenced modules〞each keeps functions small and annotated for easier comprehension.
