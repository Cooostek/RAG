#управление состоянием ()
#сохранение/загрузку состояния пайплайна (например, хеш документов, версия коллекции Milvus)
import json
import os
from app.core.config import settings
from app.storage.files import ensure_dir

STATE_FILE = f"{settings.STATE_DIR}/pipeline_state.json"

def load_state():
    ensure_dir(settings.STATE_DIR)
    if not os.path.exists(STATE_FILE):
        return {}
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_state(state: dict):
    ensure_dir(settings.STATE_DIR)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)