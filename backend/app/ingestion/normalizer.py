#подготовить текст для эмбеддинга и поиска, добавить метаданные

# все документы приводятся к структуре «вопрос–ответ–код»
#пустые описания заменяются заглушкой, документы без keyword отбрасываются
#доп метаданные для фильтрации и упрощения поиска
#search_text — цельный текст, который можно подавать в модель для создания векторов

from typing import List, Dict

def normalize_documents(rows: List[Dict]) -> List[Dict]:
    normalized = []

    for row in rows:
        keyword = (row.get("keyword") or "").strip()
        description = (row.get("description") or "").strip()
        code = (row.get("code") or "").strip()

        if not keyword:
            continue

        text_parts = [f"Вопрос: {keyword}"]
        text_parts.append(f"Ответ: {description if description else '(описание отсутствует)'}")
        if code:
            text_parts.append(f"Пример кода:\n{code}")

        search_text = "\n".join(text_parts)

        metadata = {
            "doc_id": row["doc_id"],
            "keyword": keyword,
            "page_title": row.get("page_title", ""),
            "source_url": row.get("source_url", ""),
            "has_code": bool(code),
            "length": len(search_text),
            "words": len(search_text.split()),
            "updated_at": row.get("updated_at")
        }

        normalized.append({
            "doc_id": row["doc_id"],
            "text": search_text,
            "metadata": metadata
        })

    return normalized