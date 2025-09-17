# Contract Clause Risk Detection System

A Flask-based assistant that flags risky clauses inside uploaded contracts. The app wraps an NLP classifier (fine-tuned LegalBERT for Malaysian contracts) with a polished UI, quick summaries, and history management.

## Highlights
- Upload PDF or DOCX files and receive clause-level risk flags
- Colour-coded category breakdown with plain-language explanations
- Gemini AI integration for on-demand clause summaries (optional)
- History screen with re-analyse/delete actions; deleting also removes the original upload and generated reports
- Export HTML/PDF reports or download highlighted PDFs

## Prerequisites
- Python 3.9 or newer
- `pip` / `virtualenv`
- Access to the public Hugging Face model [`StudySeur/LegalBERT-finetuning-Malaysia`](https://huggingface.co/StudySeur/LegalBERT-finetuning-Malaysia) (download happens automatically)
- (Optional) Google Gemini API key for AI explanations

## Quick Start
```bash
git clone <your-repo-url>
cd "RiskClauseDetection"
python -m venv .venv
.venv\Scripts\activate  # On macOS/Linux use: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` with your own values:

```dotenv
FLASK_APP=run.py
FLASK_ENV=development
FLASK_RUN_PORT=8000
SECRET_KEY=your-secret
DATABASE_PATH=app.db
MODEL_NAME_OR_PATH=StudySeur/LegalBERT-finetuning-Malaysia
GEMINI_API_KEY=optional-api-key
```

Then start the dev server:

```bash
flask run --port 8000
```

Visit `http://localhost:8000` to use the app.

## Environment Variables
| Name | Description |
| ---- | ----------- |
| `FLASK_APP` | Entry point for Flask CLI (`run.py`). |
| `FLASK_ENV` | `development` or `production`. |
| `FLASK_RUN_PORT` | HTTP port (defaults to 5000 if unset). |
| `SECRET_KEY` | Flask session secret; generate a strong random string. |
| `DATABASE_PATH` | SQLite database location. |
| `MODEL_NAME_OR_PATH` | Hugging Face repo or local path to the classifier. |
| `GEMINI_API_KEY` | Optional key enabling Gemini explanations. |

## Project Structure
```
app/
  blueprints/        # Flask blueprints (analyze, history, settings)
  templates/         # Jinja templates
  static/            # CSS/JS assets
  models.py          # SQLAlchemy models
  services/          # NLP, PDF highlighting, summariser helpers
uploads/             # Uploaded contracts (ignored by Git)
reports/             # Generated exports (ignored by Git)
```

## Testing
Run unit or integration tests once they are added:
```bash
pytest
```

## Notes
- Deleting an analysis in the History page removes the uploaded file and any generated reports when it is the last analysis for that contract.
- Reports and uploads are ignored by Git but retained locally for review.
- Gemini-based explanations are optional; disable them via the Settings screen or leave `GEMINI_API_KEY` unset.

## License
MIT
