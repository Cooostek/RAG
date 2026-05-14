#полное обновление базы знаний от парсинга до индексации эмбедингов

import hashlib
import os
from datetime import datetime

from pymilvus import connections, utility

from app.core.config import settings
from app.core.logger import setup_logger
from app.core.metrics import MetricsLogger
from app.ingestion.parser import MicroImParser
from app.ingestion.normalizer import normalize_documents
from app.ingestion.embedder import HybridEmbedder
from app.ingestion.milvus_indexer import MilvusIndexer
from app.storage.files import save_jsonl
from app.storage.state import load_state, save_state

logger = setup_logger("pipeline")
metrics = MetricsLogger("ingestion_metrics.json")


def _hash_docs(docs: list) -> str:
    raw = "".join(sorted([d["doc_id"] for d in docs]))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _milvus_has_alias_or_collection(name: str) -> bool:
    """
    В Milvus alias с точки зрения pymilvus выглядит как "collection exists".
    Поэтому достаточно has_collection(name).
    """
    try:
        connections.connect("default", host=settings.MILVUS_HOST, port=settings.MILVUS_PORT)
        return bool(utility.has_collection(name))
    except Exception as e:
        logger.warning(f"Milvus check failed: {e}")
        return False


def run_full_pipeline(force=False):
    start = datetime.utcnow()
    logger.info(f"Pipeline start. force={force}")

    parser = MicroImParser()
    raw_docs = parser.run()

    if not raw_docs:
        logger.warning("Парсер не вернул данных")
        metrics.log({"type": "ingestion", "status": "no_data"})
        return {"status": "no_data"}

    docs_hash = _hash_docs(raw_docs)
    state = load_state()
    last_hash = state.get("last_docs_hash")

    raw_jsonl = f"{settings.RAW_DIR}/parsed_latest.jsonl"
    os.makedirs(settings.RAW_DIR, exist_ok=True)
    save_jsonl(raw_jsonl, raw_docs)

    alias_exists = _milvus_has_alias_or_collection(settings.MILVUS_COLLECTION_ALIAS)
    if (not alias_exists) and (not force):
        logger.warning(f"Milvus пустой/алиас '{settings.MILVUS_COLLECTION_ALIAS}' не найден -> форсирую переиндексацию")
        force = True

    if (not force) and last_hash == docs_hash:
        logger.info("Изменений в данных нет, переиндексация не нужна")
        metrics.log({
            "type": "ingestion",
            "status": "skipped_no_changes",
            "docs_count": len(raw_docs),
            "hash": docs_hash
        })
        return {"status": "skipped_no_changes", "docs_count": len(raw_docs)}

    logger.info("Нормализация документов...")
    normalized = normalize_documents(raw_docs)

    processed_jsonl = f"{settings.PROCESSED_DIR}/normalized_latest.jsonl"
    os.makedirs(settings.PROCESSED_DIR, exist_ok=True)
    save_jsonl(processed_jsonl, normalized)

    texts = [d["text"] for d in normalized]
    version = "knowledge_base_v" + datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    logger.info("Embedder: fit_sparse (TF-IDF)...")
    embedder = HybridEmbedder()
    embedder.fit_sparse(texts)

    logger.info("Embedder: create_dense...")
    dense = embedder.create_dense(texts)

    logger.info("Embedder: create_sparse...")
    sparse = embedder.create_sparse(texts)

    logger.info("Embedder: save_artifacts...")
    embedder.save_artifacts(dense, sparse, version)

    logger.info(f"Milvus: insert_documents -> {version} ...")
    indexer = MilvusIndexer()
    indexer.insert_documents(version, normalized, dense, sparse)

    logger.info(f"Milvus: switch_alias {settings.MILVUS_COLLECTION_ALIAS} -> {version}")
    indexer.switch_alias(version, settings.MILVUS_COLLECTION_ALIAS)

    logger.info("Milvus: cleanup_old_collections...")
    indexer.cleanup_old_collections(prefix="knowledge_base_v", keep_latest=2)

    state.update({
        "last_docs_hash": docs_hash,
        "last_collection_version": version,
        "last_ingestion_at": datetime.utcnow().isoformat(),
        "docs_count": len(normalized)
    })
    save_state(state)

    elapsed = (datetime.utcnow() - start).total_seconds() * 1000
    metrics.log({
        "type": "ingestion",
        "status": "success",
        "docs_count": len(normalized),
        "collection_version": version,
        "duration_ms": round(elapsed, 2)
    })

    logger.info(f"Pipeline завершен: {version}, docs={len(normalized)}")
    return {"status": "success", "collection_version": version, "docs_count": len(normalized)}