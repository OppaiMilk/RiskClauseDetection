from flask import Blueprint

bp = Blueprint("analyze", __name__)

from . import routes  # noqa: E402,F401

