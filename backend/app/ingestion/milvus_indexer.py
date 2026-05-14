#создание, индексация и управление коллекциями векторов в Milvus

import numpy as np
from pymilvus import connections, FieldSchema, CollectionSchema, DataType, Collection, utility
from app.core.config import settings
from app.core.logger import setup_logger

logger = setup_logger("milvus_indexer")

class MilvusIndexer:
    def __init__(self):
        connections.connect("default", host=settings.MILVUS_HOST, port=settings.MILVUS_PORT)

    #подготовка разрежённых векторов
    #Преобразует разрежённую матрицу в список словарей {индекс: значение} те формат милвуса
    def _prepare_sparse_vectors(self, sparse_embeddings):
        sparse_vectors = []
        sparse_embeddings = sparse_embeddings.tocsr()
        empty_count = 0

        for i in range(sparse_embeddings.shape[0]):
            row = sparse_embeddings.getrow(i)
            if row.nnz == 0:
                empty_count += 1
                sparse_vectors.append({0: 0.001})
                continue

            sparse_dict = {
                int(idx): float(val)
                for idx, val in zip(row.indices, row.data)
                if abs(val) > 1e-8
            }
            if not sparse_dict:
                empty_count += 1
                sparse_dict = {0: 0.001}
            sparse_vectors.append(sparse_dict)

        if empty_count:
            logger.warning(f"Пустых sparse векторов исправлено: {empty_count}")

        return sparse_vectors

    #расчёт «качества» текстов
    """
        Присваивает каждому тексту вес (score) на основе:
        длины текста (бонус за 100–5000 символов, штраф за >5000 или <50 символов);
        наличия фразы "Пример кода:" (бонус);
    """
    def _quality_scores(self, texts):
        scores = []
        for t in texts:
            score = 1.0
            length = len(t)
            if 100 <= length <= 5000:
                score *= 1.2
            elif length > 5000:
                score *= 0.9
            if "Пример кода:" in t:
                score *= 1.1
            if length < 50:
                score *= 0.5
            scores.append(min(score, 2.0))
        return scores

    #создание коллекции
    def create_collection(self, collection_name: str, dense_dim: int):
        if utility.has_collection(collection_name):
            utility.drop_collection(collection_name)

        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="dense_embedding", dtype=DataType.FLOAT_VECTOR, dim=dense_dim),
            FieldSchema(name="sparse_embedding", dtype=DataType.SPARSE_FLOAT_VECTOR),
            FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=10000),
            FieldSchema(name="metadata", dtype=DataType.JSON),
            FieldSchema(name="quality_score", dtype=DataType.FLOAT),
        ]

        schema = CollectionSchema(fields, description="Hybrid knowledge base")
        collection = Collection(collection_name, schema, consistency_level="Strong")
        return collection

    #построение индексов
    def build_indexes(self, collection: Collection):
        logger.info("Создание индексов...")

        collection.create_index(
            #Для плотных векторов
            field_name="dense_embedding",
            index_params={
                "index_type": "IVF_FLAT",
                "metric_type": "COSINE", #косинусное расстояние
                "params": {"nlist": 1024} #количество кластеров для IVF
            }
        )

        collection.create_index(
            #Для разрежённых векторов
            field_name="sparse_embedding",
            index_params={
                "index_type": "SPARSE_INVERTED_INDEX",
                "metric_type": "IP", #скалярное произведение
                "params": {"drop_ratio_build": 0.1} #оптимизация построения индекса
            }
        )

        collection.load()
        logger.info("Индексы созданы, коллекция загружена")

    def insert_documents(self, collection_name: str, docs: list, dense_embeddings, sparse_embeddings):
        texts = [d["text"][:10000] for d in docs]
        metadata_list = [d["metadata"] for d in docs]
        quality_scores = self._quality_scores(texts)

        collection = self.create_collection(collection_name, dense_embeddings.shape[1])
        sparse_vectors = self._prepare_sparse_vectors(sparse_embeddings)

        entities = [
            dense_embeddings.tolist(),
            sparse_vectors,
            texts,
            metadata_list,
            quality_scores
        ]

        logger.info(f"Вставка {len(texts)} записей в {collection_name}...")
        collection.insert(entities)
        collection.flush()

        self.build_indexes(collection)
        return collection

    def switch_alias(self, new_collection_name: str, alias_name: str):
        logger.info(f"Переключение alias {alias_name} -> {new_collection_name}")
        try:
            # Если alias уже есть - переведем его на новую коллекцию
            utility.alter_alias(new_collection_name, alias_name)
        except Exception:
            # Если alias еще нет
            try:
                utility.create_alias(new_collection_name, alias_name)
            except Exception:
                # fallback: удалить и создать заново
                try:
                    utility.drop_alias(alias_name)
                except Exception:
                    pass
                utility.create_alias(new_collection_name, alias_name)

    def cleanup_old_collections(self, prefix="knowledge_base_v", keep_latest=2):
        all_collections = utility.list_collections()
        targets = sorted([c for c in all_collections if c.startswith(prefix)])
        if len(targets) <= keep_latest:
            return

        to_delete = targets[:-keep_latest]
        for col_name in to_delete:
            logger.info(f"Удаление старой коллекции: {col_name}")
            try:
                utility.drop_collection(col_name)
            except Exception as e:
                logger.warning(f"Не удалось удалить {col_name}: {e}")