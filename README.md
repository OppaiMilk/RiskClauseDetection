# README.md
# Contract Clause Risk Detection System

A Flask web application for analyzing contract documents, detecting risk clauses, and providing summaries. Uses NLP models (e.g., Legal-BERT) for clause classification.

## Features
- Upload contract files (PDF/DOCX)
- Analyze contracts for risky clauses
- View analysis history and top risk categories
- Re-analyze contracts with updated models/settings
- Delete analyses
- Customizable risk weights and thresholds

## Requirements
- Python 3.8+
- Flask
- Flask-SQLAlchemy
- python-dotenv

## Setup

1. Clone the repository:
   ```
   git clone <your-repo-url>
   cd CodeX-FYP
   ```

2. Create a virtual environment and activate it:
   ```
   python -m venv venv
   venv\Scripts\activate
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Set environment variables (optional, see `.env.example`):
   ```
   cp .env.example .env
   ```

5. Run the application:
   ```
   flask run
   ```

## Usage
- Access the app at `http://localhost:5000`
- Upload contracts, view analyses, and adjust settings as needed.

## Folder Structure
- `app/` - Main application code
- `app/models.py` - Database models
- `app/blueprints/` - Modular route handlers
- `app/templates/` - HTML templates
- `app/static/` - Static files

## License
MIT