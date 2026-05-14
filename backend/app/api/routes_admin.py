#ПРИНУДИТЕЛЬНОЕ ОБНОВЛЕНИЕ ВБД

from flask import Blueprint, jsonify, request
from app.ingestion.pipeline import run_full_pipeline

bp_admin = Blueprint("admin", __name__)

@bp_admin.route("/admin/reindex", methods=["POST"])
def reindex():
    data = request.get_json(silent=True) or {}
    force = bool(data.get("force", False))
    result = run_full_pipeline(force=force)
    return jsonify(result)