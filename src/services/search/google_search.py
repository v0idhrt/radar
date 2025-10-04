# Google Custom Search API Service

from typing import List, Optional
from datetime import datetime

from src.services.search.base import BaseSearchService
from src.models.news import News
from src.core.config import config
from ..logging_service import get_logger

logger = get_logger(__name__)


# Google Search Service
class GoogleSearchService(BaseSearchService):
    """Google Custom Search API implementation"""

    def __init__(self):
        super().__init__()
        self.api_key = config.GOOGLE_API_KEY
        self.cx = config.GOOGLE_CX
        self.base_url = "https://www.googleapis.com/customsearch/v1"

    def is_configured(self) -> bool:
        """Check if Google Search API is configured"""
        return bool(self.api_key and self.cx)

    def search(
        self,
        company_name: str,
        max_results: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[News]:
        """
        Search for company news using Google Custom Search API

        Args:
            company_name: Company name to search
            max_results: Maximum results to return
            start_date: Optional start date for search results
            end_date: Optional end date for search results

        Returns:
            List of News objects
        """
        if not self.is_configured():
            logger.warning("Google Search API не настроен, поиск недоступен")
            return []

        max_results = max_results or self.max_results
        news_items = []
        seen_urls = set()

        logger.info(
            "Запуск Google Custom Search для '%s' (max_results=%s, start_date=%s, end_date=%s)",
            company_name,
            max_results,
            start_date,
            end_date
        )

        query_variants = self._build_query_variants(company_name)

        if self.deep_search:
            logger.debug(
                "Глубокий поиск Google активирован (%s вариантов запроса)",
                len(query_variants),
            )

        # Google Custom Search returns max 10 results per request
        for search_query in query_variants:
            if len(news_items) >= max_results:
                break

            remaining = max_results - len(news_items)
            num_requests = (remaining + 9) // 10

            for page in range(num_requests):
                if len(news_items) >= max_results:
                    break

                start_index = page * 10 + 1

                params = {
                    'key': self.api_key,
                    'cx': self.cx,
                    'q': search_query,
                    'num': min(10, max_results - len(news_items)),
                    'start': start_index,
                    'dateRestrict': 'y1' if self.deep_search else 'm6',
                    'hl': 'ru',
                    'lr': 'lang_ru',
                    'gl': 'ru'
                }

                if start_date and end_date:
                    try:
                        params['sort'] = f"date:r:{start_date.strftime('%Y%m%d')}:{end_date.strftime('%Y%m%d')}"
                    except Exception:
                        logger.debug("Не удалось сформировать sort параметр для Google", exc_info=True)

                data = self._make_request(self.base_url, params=params)

                if not data or 'items' not in data:
                    logger.debug(
                        "Пустой ответ от Google Search для запроса '%s' (страница %s)",
                        search_query,
                        page + 1,
                    )
                    break

                for item in data['items']:
                    url = item.get('link', '')
                    if not url or url in seen_urls:
                        continue

                    publish_date = self._extract_publish_date(item)

                    # Get content: use snippet or fetch full article
                    content = item.get('snippet', '')
                    html_date = None

                    if self.fetch_full_content and url:
                        full_content, html_date = self._fetch_full_article_content(url)
                        if full_content:
                            content = full_content
                        if html_date and not publish_date:
                            publish_date = html_date

                    source_label = self._extract_source_label(item, url)
                    news_item = self._create_news_item(
                        company_name=company_name,
                        title=self._clean_text(item.get('title', '')),
                        content=self._clean_text(content),
                        url=url,
                        source=source_label,
                        publish_date=publish_date
                    )
                    news_items.append(news_item)
                    seen_urls.add(url)

                    if len(news_items) >= max_results:
                        break

        logger.info(
            "Google Custom Search завершён для '%s'. Найдено %s материалов",
            company_name,
            len(news_items),
        )

        return news_items

    def _extract_source_label(self, item: dict, fallback_url: str) -> str:
        pagemap = item.get('pagemap', {}) if isinstance(item, dict) else {}

        metatags = pagemap.get('metatags') or []
        if isinstance(metatags, dict):
            metatags = [metatags]

        label_keys = (
            'og:site_name',
            'twitter:site',
            'twitter:creator',
            'application-name',
            'publisher',
        )

        for meta in metatags:
            if not isinstance(meta, dict):
                continue
            for key in label_keys:
                value = meta.get(key)
                if value:
                    cleaned = value.strip()
                    if cleaned.startswith('@'):
                        cleaned = cleaned[1:]
                    if cleaned:
                        return cleaned

        source = item.get('displayLink') or item.get('htmlFormattedUrl') or ''
        if isinstance(source, str) and source:
            cleaned = source.replace('www.', '').strip()
            return cleaned.split('/')[0] if '/' in cleaned else cleaned

        if fallback_url:
            try:
                from urllib.parse import urlparse
                parsed = urlparse(fallback_url)
                netloc = parsed.netloc.replace('www.', '').strip()
                return netloc or 'unknown'
            except Exception:
                pass

        return 'unknown'

    def _extract_publish_date(self, item: dict) -> Optional[datetime]:
        pagemap = item.get('pagemap', {}) if isinstance(item, dict) else {}

        # Helper to try parsing a string into datetime
        # 1. meta tags (article/news schema)
        metatags = pagemap.get('metatags') or []
        if isinstance(metatags, dict):
            metatags = [metatags]
        meta_keys = (
            'article:published_time',
            'article:modified_time',
            'og:updated_time',
            'datePublished',
            'dateModified',
            'pubdate',
            'lastmod',
        )
        for meta in metatags:
            if not isinstance(meta, dict):
                continue
            for key in meta_keys:
                dt = self._parse_date_value(meta.get(key))
                if dt:
                    return dt

        # 2. structured data blocks
        structured_sources = (
            pagemap.get('newsarticle') or [],
            pagemap.get('article') or [],
            pagemap.get('blogposting') or [],
        )
        struct_keys = (
            'datePublished',
            'dateModified',
            'datemodified',
            'datepublished',
        )
        for block in structured_sources:
            if isinstance(block, dict):
                block = [block]
            for entry in block:
                if not isinstance(entry, dict):
                    continue
                for key in struct_keys:
                    dt = self._parse_date_value(entry.get(key))
                    if dt:
                        return dt

        # 3. top-level fields sometimes contain ISO dates
        for key in ('date', 'publisheddate'):
            dt = self._parse_date_value(item.get(key))
            if dt:
                return dt

        # 4. Fallback: try to extract from visible text
        for text in (item.get('title'), item.get('snippet')):
            dt = self._parse_date_value(text)
            if dt:
                return dt

        return None
