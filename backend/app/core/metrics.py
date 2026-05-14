#логи для метрик(сохраняет статистические данные)

import json
import os
from datetime import datetime
from app.core.config import settings

class MetricsLogger:
    def __init__(self, log_file="metrics.json"):
        os.makedirs(settings.LOGS_DIR, exist_ok=True)
        self.log_path = os.path.join(settings.LOGS_DIR, log_file)
        if not os.path.exists(self.log_path):
            with open(self.log_path, "w", encoding="utf-8") as f:
                json.dump([], f, ensure_ascii=False, indent=2)

    #запись метрик
    def log(self, payload: dict):
        payload = dict(payload)
        payload.setdefault("timestamp", datetime.utcnow().isoformat())

        try:
            with open(self.log_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = []

        data.append(payload)

        with open(self.log_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    #получение последних записей
    def tail(self, n=20):
        try:
            with open(self.log_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data[-n:]
        except Exception:
            return []