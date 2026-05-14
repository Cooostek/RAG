#проверка здоровья

from flask import Blueprint, jsonify
from app.search.engine import HybridSearchEngine
from app.core.metrics import MetricsLogger

bp_health = Blueprint("health", __name__)
engine = HybridSearchEngine()

@bp_health.route("/health", methods=["GET"])
def health():
    info = engine.health()
    if "error" in info:
        return jsonify({"status": "unhealthy", **info}), 503
    return jsonify({"status": "healthy", **info})

#метрики (поиск + генерация ответов + индексация)
#возвращает JSON с последними метриками по каждому этапу
@bp_health.route("/metrics", methods=["GET"])
def metrics():
    search_m = MetricsLogger("search_metrics.json").tail(10)
    gen_m = MetricsLogger("generation_metrics.json").tail(10)
    ing_m = MetricsLogger("ingestion_metrics.json").tail(10)

    return jsonify({
        "search_latest": search_m,
        "generation_latest": gen_m,
        "ingestion_latest": ing_m
    })

#возвращает все доступные эндпоинты
@bp_health.route("/", methods=["GET"])
def index():
    return jsonify({
        "message": "RAG Search API",
        "endpoints": {
            "POST /ask": "Поиск + генерация",
            "POST /search": "Только поиск",
            "POST /admin/reindex": "Ручная переиндексация",
            "GET /health": "Статус",
            "GET /metrics": "Метрики"
        }
    })