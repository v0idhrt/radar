# Yandex Cloud Search API Service

from typing import List, Optional
from datetime import datetime
from dateutil import parser as date_parser

from src.services.search.base import BaseSearchService
from src.models.news import News
from src.core.config import config
import base64, xml.etree.ElementTree as ET
from ..logging_service import get_logger
import requests

logger = get_logger(__name__)


class YandexSearchService(BaseSearchService):
    """Yandex Cloud Web Search v2"""
    def __init__(self):
        super().__init__()
        self.api_key = config.YANDEX_API_KEY
        self.folder_id = config.YANDEX_FOLDER_ID
        self.endpoint = "https://searchapi.api.cloud.yandex.net/v2/web/search"
        # если в окружении прописан прокси — отключим его только для этого клиента
        self.session = requests.Session()
        self.session.trust_env = False

    def is_configured(self) -> bool:
        return bool(self.api_key and self.folder_id)

    def _get_domain_chunks(self) -> List[Optional[List[str]]]:
        if not self.preferred_domains:
            return [None]

        # Yandex has strict limits: max 40 WORDS and 400 chars
        # Each "site:domain.ru OR" = ~3 words, so max 3-4 domains per query
        chunk_size = 3 if self.deep_search else 2
        chunks = [
            self.preferred_domains[i:i + chunk_size]
            for i in range(0, len(self.preferred_domains), chunk_size)
        ]

        # Start with unfiltered query for better coverage
        return [None] + chunks

    def search(
        self,
        company_name: str,
        max_results: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[News]:
        if not self.is_configured():
            logger.warning("Yandex Cloud Search API не настроен")
            return []

        max_results = max_results or self.max_results
        logger.info("Yandex v2 search '%s' (max=%s)", company_name, max_results)

        news_items: List[News] = []
        seen_urls = set()
        query_variants = self._build_query_variants(company_name)

        if self.deep_search:
            logger.debug(
                "Глубокий поиск Yandex активирован (%s вариантов запроса)",
                len(query_variants),
            )

        for search_query in query_variants:
            if len(news_items) >= max_results:
                break

            payload = {
                "query": {
                    "searchType": "SEARCH_TYPE_RU",
                    "queryText": search_query
                },
                "folderId": self.folder_id,
                "responseFormat": "FORMAT_XML",
                "userAgent": self.user_agent
            }

            try:
                r = self.session.post(
                    self.endpoint,
                    json=payload,
                    headers={"Authorization": f"Api-Key {self.api_key}"},
                    timeout=self.timeout,
                    proxies={},
                )
                r.raise_for_status()
                data = r.json()

                logger.debug("Yandex v2 ответ: %s", data)
                xml_b64 = data.get("response", {}).get("rawData") or data.get("rawData")
                if not xml_b64:
                    logger.warning(
                        "Yandex v2 вернул пустой rawData: %s",
                        data.get("response"),
                    )
                    continue

                xml_text = base64.b64decode(xml_b64).decode("utf-8", "ignore")
                remaining = max_results - len(news_items)
                parsed_items = self._parse_xml(company_name, xml_text, remaining)

                for item in parsed_items:
                    if item.url in seen_urls:
                        continue
                    news_items.append(item)
                    seen_urls.add(item.url)

                    if len(news_items) >= max_results:
                        break

            except requests.exceptions.RequestException as e:
                response = getattr(e, 'response', None)
                if response is not None:
                    try:
                        logger.error(
                            "Yandex v2 HTTP error: %s | body=%s",
                            e,
                            response.text,
                            exc_info=e,
                        )
                    except Exception:
                        logger.error("Yandex v2 HTTP error: %s", e, exc_info=e)
                else:
                    logger.error("Yandex v2 HTTP error: %s", e, exc_info=e)
                continue
            except Exception as e:
                logger.error("Yandex v2 parse error: %s", e, exc_info=e)
                continue

        logger.debug("Yandex v2 парсинг XML завершён: %d результатов", len(news_items))
        return news_items

    # --- разбор XML, максимально близко к твоей логике ---
    def _parse_xml(self, company_name: str, xml_text: str, max_results: int) -> List[News]:
        def strip_tag(tag: str) -> str:
            return tag.rsplit('}', 1)[-1] if '}' in tag else tag

        def find_first(el, name: str):
            for ch in list(el):
                if strip_tag(ch.tag) == name:
                    return ch
            for ch in el.iter():
                if ch is el:
                    continue
                if strip_tag(ch.tag) == name:
                    return ch
            return None

        def find_text(el, name: str) -> str:
            node = find_first(el, name)
            return (node.text or "").strip() if node is not None else ""

        news_items: List[News] = []
        root = ET.fromstring(xml_text)
        groups = [g for g in root.iter() if strip_tag(g.tag) == "group"]

        for g in groups:
            doc = find_first(g, "doc")
            if doc is None:
                continue

            url_value = find_text(doc, "url")
            title_value = find_text(doc, "title") or find_text(doc, "headline")
            if not url_value or not title_value:
                continue

            passages = [p for p in doc.iter() if strip_tag(p.tag) == "passage"]
            content = " ".join(filter(None, [self._strip_html((p.text or "").strip()) for p in passages]))

            publish_date = None
            ts = find_text(doc, "modtime") or find_text(doc, "freshness")
            if ts:
                try:
                    publish_date = date_parser.parse(ts)
                except Exception:
                    publish_date = None

            # Fetch full article content if enabled
            if self.fetch_full_content and url_value:
                full_content, html_date = self._fetch_full_article_content(url_value)
                if full_content:
                    content = full_content
                # Use HTML date if available and XML date is missing
                if html_date and not publish_date:
                    publish_date = html_date

            news_items.append(self._create_news_item(
                company_name=company_name,
                title=self._clean_text(self._strip_html(title_value) or title_value),
                content=self._clean_text(content or self._strip_html(title_value) or title_value),
                url=url_value,
                source="yandex",
                publish_date=publish_date
            ))
            if len(news_items) >= max_results:
                break

        logger.debug("Yandex v2 готово: %d результатов", len(news_items))
        return news_items

    def _strip_html(self, text: str) -> str:
        import re
        return re.sub(r"<[^>]+>", "", text)
