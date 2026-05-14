#работа с JSONL это формат, где каждая строка — отдельный JSON-объект

import json
import os
from typing import List, Dict

def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)

def save_jsonl(path: str, rows: List[Dict]):
    ensure_dir(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

def load_jsonl(path: str) -> List[Dict]:
    rows = []
    if not os.path.exists(path):
        return rows
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows