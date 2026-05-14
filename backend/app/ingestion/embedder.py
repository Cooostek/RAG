#гибридное встраивание 

    """
    Dense (SentenceTransformer) — 
    хорошо ловит семантику, но требует больше памяти.
    
    Sparse (TF‑IDF) — 
    эффективен для поиска по ключевым словам, компактен.
    """


import os
import joblib
import numpy as np
import scipy.sparse as sp
from sentence_transformers import SentenceTransformer
from sklearn.feature_extraction.text import TfidfVectorizer

from app.core.config import settings
from app.core.logger import setup_logger

logger = setup_logger("embedder")

class HybridEmbedder:
    #модель можно поменять есть куча других
    def __init__(self, model_name="intfloat/multilingual-e5-base"):
        os.makedirs(settings.MODELS_DIR, exist_ok=True)
        self.model_name = model_name
        self.dense_model = SentenceTransformer(model_name)
        self.sparse_vectorizer = TfidfVectorizer(
            max_features=50000,
            ngram_range=(1, 2),
            min_df=1
        )
    
    #модель учится распознавать важные слова и их комбинации (для sparse embeddings)
    def fit_sparse(self, texts):
        logger.info("Обучение TF-IDF vectorizer...")
        self.sparse_vectorizer.fit(texts)
    
    #генерация плотных эмбеддингов
    def create_dense(self, texts):
        e5_texts = [f"passage: {t}" for t in texts]
        logger.info("Создание dense embeddings...")
        dense = self.dense_model.encode(
            e5_texts,
            batch_size=32,
            show_progress_bar=True,
            normalize_embeddings=True
        )
        return np.asarray(dense, dtype=np.float32)

    #генерация разрежённых эмбеддингов
    def create_sparse(self, texts):
        logger.info("Создание sparse embeddings...")
        return self.sparse_vectorizer.transform(texts)

    def save_artifacts(self, dense, sparse, collection_version):
        dense_path = f"{settings.PROCESSED_DIR}/{collection_version}_dense.npy"
        sparse_path = f"{settings.PROCESSED_DIR}/{collection_version}_sparse.npz"
        vectorizer_path = f"{settings.MODELS_DIR}/tfidf_vectorizer.pkl"

        os.makedirs(settings.PROCESSED_DIR, exist_ok=True)
        np.save(dense_path, dense)
        sp.save_npz(sparse_path, sparse)
        joblib.dump(self.sparse_vectorizer, vectorizer_path)

        logger.info(f"Dense сохранен: {dense_path}")
        logger.info(f"Sparse сохранен: {sparse_path}")
        logger.info(f"Vectorizer сохранен: {vectorizer_path}")

        return dense_path, sparse_path, vectorizer_path