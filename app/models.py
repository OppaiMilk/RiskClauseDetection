from datetime import datetime
from . import db


class Contract(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    path = db.Column(db.String(512), nullable=False)
    file_hash = db.Column(db.String(64), index=True)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    num_pages = db.Column(db.Integer, default=0)

    analyses = db.relationship("Analysis", backref="contract", cascade="all, delete-orphan")


class Analysis(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    contract_id = db.Column(db.Integer, db.ForeignKey("contract.id"), nullable=False)
    model_name = db.Column(db.String(255))
    model_version = db.Column(db.String(100))
    total_hits = db.Column(db.Integer, default=0)
    finished_at = db.Column(db.DateTime, default=datetime.utcnow)

    hits = db.relationship("Hit", backref="analysis", cascade="all, delete-orphan")
    summaries = db.relationship("Summary", backref="analysis", cascade="all, delete-orphan")


class Hit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    analysis_id = db.Column(db.Integer, db.ForeignKey("analysis.id"), nullable=False)
    category = db.Column(db.String(64), index=True)
    prob = db.Column(db.Float)
    page_no = db.Column(db.Integer)
    start_char = db.Column(db.Integer)
    end_char = db.Column(db.Integer)
    text_excerpt = db.Column(db.Text)
    ambiguous = db.Column(db.Boolean, default=False)


class Summary(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    analysis_id = db.Column(db.Integer, db.ForeignKey("analysis.id"), nullable=False)
    output_text = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

