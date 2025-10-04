# Serper.dev Search API Service

from typing import List, Optional

from src.services.search.base import BaseSearchService
from src.models.news import News
from src.core.config import config
from ..logging_service import get_logger
from datetime import datetime

logger = get_logger(__name__)


# Serper Search Service
class SerperSearchService(BaseSearchService):
    """Serper.dev Search API implementation"""

    def __init__(self):
        super().__init__()
        self.api_key = config.SERPER_API_KEY
        self.base_url = "https://google.serper.dev/news"

    def is_configured(self) -> bool:
        """Check if Serper API is configured"""
        return bool(self.api_key)
    
    def _build_query_variants(self, company_name: str) -> list[str]:
        """
        Build simple queries for Serper (doesn't support complex site operators)
        Override parent method to avoid site: operators
        """
        variations = [f"{company_name} новости"]
        
        if self.deep_search:
            variations.extend([
                f'"{company_name}" новости',
                f"{company_name}",
                f'"{company_name}"',
                f"{company_name} пресс релиз",
                f"{company_name} отчёт",
                f"{company_name} news",
                f'"{company_name}" news',
            ])
        
        return variations

    def search(
        self,
        company_name: str,
        max_results: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[News]:
        """
        Search for company news using Serper.dev API

        Args:
            company_name: Company name to search
            max_results: Maximum results to return
            start_date: Optional start date for search results
            end_date: Optional end date for search results

        Returns:
            List of News objects
        """
        if not self.is_configured():
            logger.warning("Serper API не настроен, поиск недоступен")
            return []

        max_results = max_results or self.max_results
        news_items = []
        seen_urls = set()

        logger.info(
            "Запуск Serper Search для '%s' (max_results=%s)",
            company_name,
            max_results,
        )

        import requests

        headers = {
            'X-API-KEY': self.api_key,
            'Content-Type': 'application/json'
        }

        query_variants = self._build_query_variants(company_name)

        if self.deep_search:
            logger.debug(
                "Глубокий поиск Serper активирован (%s вариантов запроса)",
                len(query_variants),
            )

        try:
            for search_query in query_variants:
                if len(news_items) >= max_results:
                    break

                payload = {
                    'q': search_query,
                    'num': min(100, max(20, max_results - len(news_items))),
                    'gl': 'ru',
                    'hl': 'ru',
                    'location': 'Russia'
                }

                logger.debug("Serper запрос: q='%s' (длина: %d)", search_query, len(search_query))

                response = requests.post(
                    self.base_url,
                    json=payload,
                    headers=headers,
                    timeout=self.timeout
                )
                
                if response.status_code != 200:
                    logger.error("Serper error %d: %s | payload: %s", response.status_code, response.text, payload)
                
                response.raise_for_status()
                data = response.json()

                for section in ('news', 'topStories', 'organic'):
                    if section not in data or len(news_items) >= max_results:
                        continue

                    for item in data.get(section, []):
                        url = item.get('link', '')
                        if not url or url in seen_urls:
                            continue

                        publish_date = self._parse_date_value(item.get('date') or item.get('datePublished'))
                        if not publish_date:
                            publish_date = (
                                self._parse_date_value(item.get('title'))
                                or self._parse_date_value(item.get('snippet'))
                            )

                        content = item.get('snippet', '')

                        if self.fetch_full_content and url:
                            full_content, html_date = self._fetch_full_article_content(url)
                            if full_content:
                                content = full_content
                            if html_date and not publish_date:
                                publish_date = html_date

                        news_item = self._create_news_item(
                            company_name=company_name,
                            title=self._clean_text(item.get('title', '')),
                            content=self._clean_text(content),
                            url=url,
                            source='serper',
                            publish_date=publish_date
                        )
                        news_items.append(news_item)
                        seen_urls.add(url)

                        if len(news_items) >= max_results:
                            break

                if len(news_items) >= max_results:
                    break

        except Exception as e:
            logger.error("Ошибка Serper Search: %s", e, exc_info=e)

        logger.info(
            "Serper Search завершён для '%s'. Найдено %s материалов",
            company_name,
            len(news_items),
        )

        return news_items
