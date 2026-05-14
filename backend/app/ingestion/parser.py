#извлекает данные и преобразует в список словарей

import hashlib
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from datetime import datetime

from app.core.config import settings
from app.core.logger import setup_logger

logger = setup_logger("parser")

class MicroImParser:
    def __init__(self):
        self.base_url = settings.PARSER_BASE_URL
        self.start_url = settings.PARSER_START_URL
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })

    def fetch(self, url: str):
        try:
            r = self.session.get(url, timeout=20)
            r.raise_for_status()
            return r.text
        except Exception as e:
            logger.error(f"Ошибка загрузки {url}: {e}")
            return None

    def parse_links(self, html: str):
        soup = BeautifulSoup(html, "html.parser")
        nav_list = soup.find("ul", class_="wp-block-list")
        if not nav_list:
            return []

        links = []
        for a in nav_list.find_all("a", href=True):
            title = a.get_text(strip=True)
            href = a["href"].strip()
            url = urljoin(self.start_url, href)
            if title and url:
                links.append({"title": title, "url": url})
        return links

    def parse_page_blocks(self, html: str, page_title: str, page_url: str):
        soup = BeautifulSoup(html, "html.parser")
        content_block = soup.find("div", class_="entry-content")
        if not content_block:
            logger.warning(f"Нет блока entry-content: {page_url}")
            return []

        header_tags = {"h2", "h3", "h4"}
        rows = []

        for header in content_block.find_all(["h2", "h3", "h4"]):
            keyword = header.get_text(strip=True)
            if not keyword:
                continue

            description_parts = []
            code_blocks = []

            next_elem = header.find_next_sibling()
            while next_elem and next_elem.name not in header_tags:
                if next_elem.name == "p":
                    txt = next_elem.get_text(" ", strip=True)
                    if txt:
                        description_parts.append(txt)

                elif next_elem.name in ["ul", "ol"]:
                    items = [li.get_text(" ", strip=True) for li in next_elem.find_all("li")]
                    items = [x for x in items if x]
                    if items:
                        description_parts.append("; ".join(items))

                elif next_elem.name == "pre":
                    code = next_elem.get_text("\n", strip=True)
                    if code:
                        code_blocks.append(code)

                elif next_elem.name == "div":
                    inner_pre = next_elem.find("pre")
                    if inner_pre:
                        code = inner_pre.get_text("\n", strip=True)
                        if code:
                            code_blocks.append(code)

                elif next_elem.name == "code":
                    code = next_elem.get_text(" ", strip=True)
                    if code:
                        code_blocks.append(code)

                next_elem = next_elem.find_next_sibling()

            description = "\n".join(description_parts).strip()
            code = code_blocks[0].strip() if code_blocks else ""

            source_text = f"{keyword}\n{description}\n{code}\n{page_url}"
            doc_id = hashlib.sha256(source_text.encode("utf-8")).hexdigest()

            #словарь с частями
            rows.append({
                "doc_id": doc_id,
                "keyword": keyword,
                "description": description,
                "code": code,
                "page_title": page_title,
                "source_url": page_url,
                "updated_at": datetime.utcnow().isoformat()
            })

        return rows

    def run(self):
        logger.info(f"Загрузка стартовой страницы: {self.start_url}")
        html = self.fetch(self.start_url)
        if not html:
            return []

        links = self.parse_links(html)
        if not links:
            logger.warning("Ссылки в меню не найдены")
            return []

        all_rows = []
        for i, link in enumerate(links, 1):
            logger.info(f"[{i}/{len(links)}] {link['title']} -> {link['url']}")
            page_html = self.fetch(link["url"])
            if not page_html:
                continue
            rows = self.parse_page_blocks(page_html, link["title"], link["url"])
            all_rows.extend(rows)

        # удаляем дубли по doc_id
        uniq = {}
        for row in all_rows:
            uniq[row["doc_id"]] = row

        result = list(uniq.values())
        logger.info(f"Парсинг завершен. Документов: {len(result)}")
        return result