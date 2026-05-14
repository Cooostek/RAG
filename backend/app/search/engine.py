#

import time
import joblib
import psutil
from datetime import datetime
from typing import List, Dict, Any

from sentence_transformers import SentenceTransformer
from pymilvus import connections, Collection

from app.core.config import settings
from app.core.logger import setup_logger
from app.core.metrics import MetricsLogger

logger = setup_logger("search_engine")


class HybridSearchEngine:
    def __init__(self):
        self.dense_model = None
        self.vectorizer = None
        self.collection = None
        self._initialized = False
        self.metrics = MetricsLogger("search_metrics.json")

    def initialize(self):
        if self._initialized:
            return

        logger.info("Инициализация поискового движка...")

        # 1) Подключаемся к Milvus и грузим коллекцию (быстро и явно)
        connections.connect("default", host=settings.MILVUS_HOST, port=settings.MILVUS_PORT)
        self.collection = Collection(settings.MILVUS_COLLECTION_ALIAS)
        self.collection.load()

        # 2) Загружаем TF-IDF vectorizer
        vectorizer_path = f"{settings.MODELS_DIR}/tfidf_vectorizer.pkl"
        self.vectorizer = joblib.load(vectorizer_path)

        # 3) Загружаем SentenceTransformer строго на CPU (фикс meta tensor)
        # max_seq_length можно уменьшить, чтобы ускорить (опционально)
        self.dense_model = SentenceTransformer(
            "intfloat/multilingual-e5-base",
            device="cpu"
        )
        # self.dense_model.max_seq_length = 256  # можно включить, если нужно быстрее

        self._initialized = True
        logger.info("Поисковый движок инициализирован")

    def _sys(self):
        mem = psutil.virtual_memory()
        return {
            "cpu_percent": psutil.cpu_percent(interval=0.05),
            "memory_percent": mem.percent,
            "memory_used_gb": round(mem.used / (1024 ** 3), 2),
        }

    def _sparse_to_dict(self, sparse_row):
        sparse_row = sparse_row.tocsr()
        if sparse_row.nnz == 0:
            return {}
        return {
            int(idx): float(val)
            for idx, val in zip(sparse_row.indices, sparse_row.data)
            if abs(val) > 1e-8
        }

    def _normalize_scores(self, score_map: dict):
        if not score_map:
            return {}
        vals = list(score_map.values())
        mn, mx = min(vals), max(vals)
        if mx - mn < 1e-9:
            return {k: 1.0 for k in score_map.keys()}
        return {k: (v - mn) / (mx - mn) for k, v in score_map.items()}

    def _safe_entity_get(self, hit, field: str, default=None):
        """
        В pymilvus entity может быть не dict.
        Делаем максимально совместимо:
        - пробуем entity.get(field) (без default!)
        - если нет, пробуем getattr(entity, field)
        """
        try:
            ent = getattr(hit, "entity", None)
            if ent is None:
                return default

            if hasattr(ent, "get"):
                val = ent.get(field)
                return default if val is None else val

            val = getattr(ent, field, None)
            return default if val is None else val
        except Exception:
            return default

    def search(self, query: str, top_k=5, alpha=None) -> List[Dict[str, Any]]:
        self.initialize()
        alpha = settings.SEARCH_ALPHA if alpha is None else float(alpha)

        if not query.strip():
            return []

        started = time.time()
        metric_payload = {
            "type": "search",
            "query": query,
            "top_k": top_k,
            "alpha": alpha,
            "system_before": self._sys(),
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Dense embed
        t0 = time.time()
        dense_query = self.dense_model.encode(
            [f"query: {query}"],
            normalize_embeddings=True
        )[0].tolist()
        dense_embed_ms = (time.time() - t0) * 1000

        # Sparse embed
        t1 = time.time()
        sparse_q = self.vectorizer.transform([query])
        sparse_dict = self._sparse_to_dict(sparse_q[0])
        sparse_embed_ms = (time.time() - t1) * 1000

        candidate_limit = max(20, top_k * 4)

        # Dense search
        t2 = time.time()
        dense_results = self.collection.search(
            data=[dense_query],
            anns_field="dense_embedding",
            param={"metric_type": "COSINE", "params": {"nprobe": 16}},
            limit=candidate_limit,
            output_fields=["text", "metadata", "quality_score"],
        )
        dense_ms = (time.time() - t2) * 1000

        # Sparse search (опционально)
        sparse_results = None
        sparse_ms = 0.0
        if sparse_dict and alpha < 1.0:
            t3 = time.time()
            try:
                sparse_results = self.collection.search(
                    data=[sparse_dict],
                    anns_field="sparse_embedding",
                    param={"metric_type": "IP", "params": {"drop_ratio_search": 0.1}},
                    limit=candidate_limit,
                    output_fields=["text", "metadata", "quality_score"],
                )
                sparse_ms = (time.time() - t3) * 1000
            except Exception as e:
                logger.warning(f"Sparse search error: {e}")
                sparse_results = None

        dense_score_map = {}
        docs = {}

        for hits in dense_results:
            for h in hits:
                doc_id = int(h.id)
                dense_score_map[doc_id] = float(h.score)
                docs[doc_id] = {
                    "id": str(doc_id),
                    "text": self._safe_entity_get(h, "text", ""),
                    "metadata": self._safe_entity_get(h, "metadata", {}) or {},
                    "quality_score": float(self._safe_entity_get(h, "quality_score", 1.0) or 1.0),
                    "dense_raw": float(h.score),
                }

        sparse_score_map = {}
        if sparse_results:
            for hits in sparse_results:
                for h in hits:
                    doc_id = int(h.id)
                    sparse_score_map[doc_id] = float(h.score)
                    if doc_id not in docs:
                        docs[doc_id] = {
                            "id": str(doc_id),
                            "text": self._safe_entity_get(h, "text", ""),
                            "metadata": self._safe_entity_get(h, "metadata", {}) or {},
                            "quality_score": float(self._safe_entity_get(h, "quality_score", 1.0) or 1.0),
                        }

        dense_norm = self._normalize_scores(dense_score_map)
        sparse_norm = self._normalize_scores(sparse_score_map)

        all_ids = set(docs.keys()) | set(sparse_score_map.keys())
        ranked = []

        for doc_id in all_ids:
            d = dense_norm.get(doc_id, 0.0)
            s = sparse_norm.get(doc_id, 0.0)
            q = float(docs[doc_id].get("quality_score", 1.0) or 1.0)

            score = (alpha * d + (1 - alpha) * s) * q

            item = dict(docs[doc_id])
            item["dense_score"] = round(d, 6)
            item["sparse_score"] = round(s, 6)
            item["score"] = round(score, 6)
            item["type"] = "hybrid" if (doc_id in dense_norm and doc_id in sparse_norm) else ("dense" if doc_id in dense_norm else "sparse")
            ranked.append(item)

        ranked.sort(key=lambda x: x["score"], reverse=True)
        ranked = ranked[:top_k]

        metric_payload.update({
            "dense_embed_ms": round(dense_embed_ms, 2),
            "sparse_embed_ms": round(sparse_embed_ms, 2),
            "dense_search_ms": round(dense_ms, 2),
            "sparse_search_ms": round(sparse_ms, 2),
            "result_count": len(ranked),
            "system_after": self._sys(),
            "total_ms": round((time.time() - started) * 1000, 2),
        })
        self.metrics.log(metric_payload)

        return ranked

    def health(self):
        try:
            self.initialize()
            return {
                "initialized": self._initialized,
                "collection_name": self.collection.name,
                "entities": self.collection.num_entities,
            }
        except Exception as e:
            return {"error": str(e)}