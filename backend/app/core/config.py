#Настройки
import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    #ВБД
    MILVUS_HOST = os.getenv("MILVUS_HOST", "127.0.0.1")
    MILVUS_PORT = os.getenv("MILVUS_PORT", "19530")
    MILVUS_COLLECTION_ALIAS = os.getenv("MILVUS_COLLECTION_ALIAS", "knowledge_base_current")

    #И снова глупая моделька, ЗАМЕНИТЕ
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3.6:latest")
    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://192.168.88.55:11434")
    OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "180"))
    
    #парсер
    PARSER_BASE_URL = os.getenv("PARSER_BASE_URL", "https://micro.im/")
    PARSER_START_URL = os.getenv("PARSER_START_URL", "https://micro.im/docs/smarty/portal-and-apps-settings")

    #поиск
    SEARCH_ALPHA = float(os.getenv("SEARCH_ALPHA", "0.6"))
    SEARCH_TOPK_DEFAULT = int(os.getenv("SEARCH_TOPK_DEFAULT", "5"))
    SEARCH_TOPK_MAX = int(os.getenv("SEARCH_TOPK_MAX", "20"))
    MAX_CONTEXT_CHARS = int(os.getenv("MAX_CONTEXT_CHARS", "7000"))

    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

    DATA_DIR = "/app/data"
    RAW_DIR = f"{DATA_DIR}/raw"
    PROCESSED_DIR = f"{DATA_DIR}/processed"
    MODELS_DIR = f"{DATA_DIR}/models"
    LOGS_DIR = f"{DATA_DIR}/logs"
    STATE_DIR = f"{DATA_DIR}/state"

settings = Settings()
