#запрос к языковой модели Ollama, используя контекст, и возвращает ответ

import os
import requests
from app.core.logger import setup_logger
from app.core.config import settings

logger = setup_logger("generator")

def ask_ollama(question: str, context: str) -> str:
    base_url = getattr(settings, "OLLAMA_BASE_URL", None) or os.getenv("OLLAMA_BASE_URL") or "http://host.docker.internal:11434"
    base_url = base_url.rstrip("/")
    #ЗАМЕНИТЬ модельку
    model = getattr(settings, "OLLAMA_MODEL", None) or os.getenv("OLLAMA_MODEL") or "llama3.2:3b"
    timeout = getattr(settings, "OLLAMA_TIMEOUT", None) or os.getenv("OLLAMA_TIMEOUT") or "180"
    timeout = int(timeout)

    prompt = (
        "Ты RAG ассистент. Отвечай кратко и по делу. "
        "Если в контексте нет ответа — скажи 'Не найдено в базе'.\n\n"
        f"КОНТЕКСТ:\n{context}\n\n"
        f"ВОПРОС:\n{question}\n\n"
        "ОТВЕТ:"
    )

    #POST-запрос к API оллама
    try:
        r = requests.post(
            f"{base_url}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=timeout,
        )
        r.raise_for_status()
        return (r.json().get("response") or "").strip() or "Пустой ответ от модели."
    except Exception as e:
        logger.error(f"Ollama error: {e}")
        return "⚠️ Ollama недоступна или модель не установлена. Проверь `ollama pull` и переменные OLLAMA_*."