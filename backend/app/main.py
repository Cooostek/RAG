#запуск Flask-приложения с API для поиска, мониторинга и админ-функций

import os
import time
import threading

from flask import Flask
from flask_cors import CORS
from pymilvus import connections, utility

from app.api.routes_search import bp_search
from app.api.routes_health import bp_health
from app.api.routes_admin import bp_admin
from app.core.logger import setup_logger
from app.search.engine import HybridSearchEngine
from app.core.config import settings

logger = setup_logger("main")


def create_app():
    app = Flask(__name__)
    CORS(app)

    app.register_blueprint(bp_search)
    app.register_blueprint(bp_health)
    app.register_blueprint(bp_admin)

    return app


app = create_app()


def _wait_for_milvus_collection(alias_name: str, timeout_sec: int = 180):
    """
    Ждем пока scheduler создаст коллекцию и/или алиас в Milvus.
    В pymilvus utility.has_collection('alias') часто возвращает True для алиаса.
    Поэтому это хороший простой чек.
    """
    started = time.time()
    last_err = None

    while time.time() - started < timeout_sec:
        try:
            connections.connect("default", host=settings.MILVUS_HOST, port=settings.MILVUS_PORT)
            if utility.has_collection(alias_name):
                return True
        except Exception as e:
            last_err = e

        time.sleep(2)

    logger.warning(f"Milvus wait timeout: alias/collection '{alias_name}' not ready. Last error: {last_err}")
    return False


def _warmup():
    try:
        logger.info("Warmup: жду Milvus + коллекцию/алиас...")

        ok = _wait_for_milvus_collection(settings.MILVUS_COLLECTION_ALIAS, timeout_sec=300)
        if not ok:
            logger.warning("Warmup: пропущен (коллекция/алиас не появился)")
            return

        logger.info("Warmup: алиас/коллекция найдены, инициализирую поисковый движок...")
        eng = HybridSearchEngine()
        eng.initialize()
        logger.info("Warmup: поисковый движок готов")

    except Exception as e:
        logger.warning(f"Warmup failed: {e}")


threading.Thread(target=_warmup, daemon=True).start()

# Запуск сервера
if __name__ == "__main__":
    logger.info("Запуск Flask API...")
    app.run(host="0.0.0.0", port=5000, debug=False)