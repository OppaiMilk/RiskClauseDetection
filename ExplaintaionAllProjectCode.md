# ExplaintaionAllProjectCode.md

## Project Overview

This project is a Flask web app for contract clause risk detection. It allows users to upload contracts, analyzes them using NLP models, and stores results in a database.

---

## Main Components

### 1. `app/__init__.py`
- Initializes Flask app and SQLAlchemy.
- Loads settings from `settings.json` (with defaults).
- Sets up folders for uploads and reports.
- Registers blueprints for modular routing.
- Injects global variables (current time, settings) into templates.

### 2. `app/models.py`
- **Contract**: Represents uploaded contract files.
- **Analysis**: Stores results of contract analysis (model name, version, risk score, etc.).
- **Hit**: Individual detected risky clauses (category, probability, excerpt).
- **Summary**: Stores summary outputs for each analysis.

### 3. `app/blueprints/history/routes.py`
- `/history/`: Lists all analyses, showing top risk category per analysis.
- `/history/<analysis_id>`: Redirects to detailed analysis result.
- `/history/<analysis_id>/reanalyze`: Re-runs analysis on the same contract file using current settings/model.
- `/history/<analysis_id>/delete`: Deletes an analysis and its associated data.

### 4. Settings
- Settings are loaded from `settings.json` and can be customized (model path, thresholds, risk weights, etc.).
- Used throughout the app for analysis and scoring.

### 5. Templates & Static Files
- HTML templates for UI (upload, analysis results, history, settings).
- Static files for CSS/JS.

---

## How Analysis Works

1. User uploads a contract.
2. The document is parsed and analyzed using an NLP model (e.g., Legal-BERT).
3. Detected risky clauses are stored as `Hit` records.
4. Each analysis is scored based on risk weights and probabilities.
5. Results are shown in the UI, with options to re-analyze or delete.

---

## Extending the Project

- Add new clause categories in `settings.json`.
- Integrate additional NLP models by updating the parser/inference services.
- Customize templates for improved UI.

---

For further details, see inline comments in each file.