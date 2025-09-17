from flask import Blueprint

bp = Blueprint("history", __name__)

from . import routes  # noqa: E402,F401

