#поиск и генерация ответов

from flask import Blueprint, request, jsonify
from app.core.config import settings
from app.core.logger import setup_logger
from app.core.metrics import MetricsLogger
from app.search.engine import HybridSearchEngine
from app.search.generator import ask_ollama

bp_search = Blueprint("search", __name__)
logger = setup_logger("routes_search")
metrics = MetricsLogger("generation_metrics.json")

_engine = None

def get_engine() -> HybridSearchEngine:
    global _engine
    if _engine is None:
        logger.info("Создаю HybridSearchEngine (первый запрос)...")
        _engine = HybridSearchEngine()
        logger.info("HybridSearchEngine создан (инициализация будет при первом поиске)")
    return _engine

@bp_search.route("/search", methods=["POST"])
def search_only():
    data = request.get_json() or {}
    query = (data.get("query") or "").strip()
    top_k = min(int(data.get("top_k", settings.SEARCH_TOPK_DEFAULT)), settings.SEARCH_TOPK_MAX)
    alpha = float(data.get("alpha", settings.SEARCH_ALPHA))

    if not query:
        return jsonify({"error": "Не указан query"}), 400

    try:
        engine = get_engine()
        results = engine.search(query, top_k=top_k, alpha=alpha)
        return jsonify({"query": query, "results_count": len(results), "results": results})
    except Exception as e:
        logger.exception("Ошибка в /search")
        return jsonify({"error": str(e)}), 500

@bp_search.route("/ask", methods=["POST"])
def ask():
    data = request.get_json() or {}

    question = (data.get("question") or "").strip()
    top_k = min(int(data.get("top_k", settings.SEARCH_TOPK_DEFAULT)), settings.SEARCH_TOPK_MAX)
    alpha = float(data.get("alpha", settings.SEARCH_ALPHA))

    # NEW: переключатель LLM
    use_llm = bool(data.get("use_llm", True))

    if not question:
        return jsonify({"error": "Нет вопроса"}), 400

    try:
        engine = get_engine()
        results = engine.search(question, top_k=top_k, alpha=alpha)
    except Exception as e:
        logger.exception("Ошибка в /ask")
        return jsonify({"error": str(e)}), 500

    if not results:
        return jsonify({"error": "Не найдено подходящего контекста"}), 404

    # контекст
    context_parts = []
    total_chars = 0
    for r in results:
        txt = r.get("text", "")
        if total_chars + len(txt) > settings.MAX_CONTEXT_CHARS:
            break
        context_parts.append(txt)
        total_chars += len(txt)
    context = "\n\n".join(context_parts)

    # NEW: если LLM выключена — просто вернем контекст (и можно сделать “extractive summary” позже)
    if not use_llm:
        return jsonify({
            "question": question,
            "answer": "LLM отключена. Ниже — найденные источники (контекст).",
            "sources": [
                {
                    "text": r.get("text", ""),
                    "score": r.get("score", 0),
                    "type": r.get("type", "hybrid"),
                    "metadata": r.get("metadata", {})
                }
                for r in results
            ]
        })

    # LLM включена
    answer = ask_ollama(question, context)

    metrics.log({
        "type": "generation",
        "question": question,
        "answer_len": len(answer),
        "context_chars": len(context),
        "top_k": top_k,
        "alpha": alpha
    })

    return jsonify({
        "question": question,
        "answer": answer,
        "sources": [
            {
                "text": r.get("text", ""),
                "score": r.get("score", 0),
                "type": r.get("type", "hybrid"),
                "metadata": r.get("metadata", {})
            }
            for r in results
        ]
    })