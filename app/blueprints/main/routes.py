from flask import render_template
from . import bp
from ...models import Analysis, Hit
from ... import db


@bp.route("/")
def index():
    # Recent analyses and simple stats
    recent = Analysis.query.order_by(Analysis.finished_at.desc()).limit(5).all()
    counts = (
        db.session.query(Hit.category, db.func.count(Hit.id))
        .group_by(Hit.category)
        .all()
    )
    data = {c: n for c, n in counts}
    total_hits = sum(data.values()) if data else 0
    return render_template("main/index.html", recent=recent, counts=data, total_hits=total_hits)

