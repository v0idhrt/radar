# News Aggregator Service

from typing import List, Optional
import asyncio
from datetime import datetime

from src.models.news import News, Company
from src.core.database import Database
from src.utils.deduplication import deduplicate_news, sort_by_relevance
from src.utils.text_processing import calculate_relevance
# Search Services
from src.services.search.google_search import GoogleSearchService
from src.services.search.yandex_search import YandexSearchService
from src.services.search.serper_search import SerperSearchService

# Social Media Parsers
from src.services.social.twitter_parser import TwitterParser
from src.services.social.telegram_parser import TelegramParser
from .logging_service import get_logger

logger = get_logger(__name__)


# News Aggregator
class NewsAggregator:
    """Aggregates news from all available sources"""

    def __init__(self, db: Optional[Database] = None):
        # Initialize search services
        self.search_services = {
            'google': GoogleSearchService(),
            'yandex': YandexSearchService(),
            'serper': SerperSearchService(),
        }

        # Initialize social parsers
        self.social_parsers = {
            'twitter': TwitterParser(),
            'telegram': TelegramParser(),
        }

        # Use shared database instance or create new one
        self.db = db if db is not None else Database()

    def get_available_sources(self) -> dict:
        """Get list of configured and available sources"""
        available = {
            'search': {},
            'social': {}
        }

        for name, service in self.search_services.items():
            available['search'][name] = service.is_configured()

        for name, parser in self.social_parsers.items():
            available['social'][name] = parser.is_configured()

        return available

    async def collect_news(
        self,
        company_name: str,
        max_results_per_source: int = 20,
        use_search: bool = True,
        use_social: bool = True,
        save_to_db: bool = True,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[News]:
        """
        Collect news from all available sources

        Args:
            company_name: Company name to search
            max_results_per_source: Max results per source
            use_search: Use search APIs
            use_social: Use social media parsers
            save_to_db: Save results to database

        Returns:
            Deduplicated list of news items
        """
        logger.info(
            "Старт агрегирования новостей для '%s' (max_results_per_source=%s, use_search=%s, use_social=%s, save_to_db=%s)",
            company_name,
            max_results_per_source,
            use_search,
            use_social,
            save_to_db,
        )

        all_news = []

        # Add/update company in database
        if save_to_db:
            company = Company(name=company_name)
            self.db.add_company(company)

        # Collect from search APIs
        if use_search:
            search_results = await self._collect_from_search(
                company_name,
                max_results_per_source,
                start_date,
                end_date
            )
            logger.info(
                "Получено %s новостей из поисковых сервисов для '%s'",
                len(search_results),
                company_name,
            )
            all_news.extend(search_results)

        # Collect from social media
        if use_social:
            social_results = await self._collect_from_social(
                company_name,
                max_results_per_source,
                start_date,
                end_date
            )
            logger.info(
                "Получено %s новостей из социальных сетей для '%s'",
                len(social_results),
                company_name,
            )
            all_news.extend(social_results)

        # Calculate relevance scores
        for news in all_news:
            if news.relevance_score is None:
                news.relevance_score = calculate_relevance(
                    news.title,
                    news.content,
                    company_name
                )

        # Deduplicate
        deduplicated = deduplicate_news(all_news)

        # Sort by relevance
        sorted_news = sort_by_relevance(deduplicated)

        # Filter by time window once and reuse
        filtered_news = self._filter_by_period(sorted_news, start_date, end_date)

        # Save to database (only entries that satisfy the window)
        if save_to_db:
            saved_count = 0
            duplicate_count = 0
            for news in filtered_news:
                result = self.db.add_news(news)
                if result:
                    saved_count += 1
                else:
                    duplicate_count += 1

            self.db.update_company_last_searched(company_name)

            logger.info(
                "Сохранено %s новых материалов по '%s' (дубликатов: %s)",
                saved_count, company_name, duplicate_count
            )

        logger.info(
            "Агрегирование для '%s' завершено. Итоговых записей: %s",
            company_name,
            len(filtered_news),
        )

        return filtered_news

    async def _collect_from_search(
        self,
        company_name: str,
        max_results: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[News]:
        """Collect from all search APIs concurrently with fallback on errors"""
        logger.debug(
            "Начинаем поиск по сервисам для '%s'", company_name
        )

        tasks = []
        service_names = []

        for name, service in self.search_services.items():
            if service.is_configured():
                # Run sync search in thread pool
                logger.debug("Запускаем поисковый сервис '%s'", name)
                task = asyncio.get_event_loop().run_in_executor(
                    None,
                    service.search,
                    company_name,
                    max_results,
                    start_date,
                    end_date
                )
                tasks.append(task)
                service_names.append(name)
            else:
                logger.debug("Поисковый сервис '%s' не настроен, пропускаем", name)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Flatten results with detailed error tracking
        all_news = []
        successful_sources = []
        failed_sources = []

        for idx, result in enumerate(results):
            service_name = service_names[idx]

            if isinstance(result, list):
                all_news.extend(result)
                successful_sources.append(service_name)
                logger.debug(
                    "Поисковый сервис '%s' успешно завершён: %s материалов",
                    service_name, len(result)
                )
            elif isinstance(result, Exception):
                failed_sources.append(service_name)
                logger.warning(
                    "Поисковый сервис '%s' завершился с ошибкой (fallback): %s",
                    service_name, result
                )

        logger.info(
            "Поисковые сервисы завершены для '%s'. Получено %s материалов "
            "(успешно: %s, ошибки: %s)",
            company_name,
            len(all_news),
            successful_sources,
            failed_sources
        )

        return all_news

    async def _collect_from_social(
        self,
        company_name: str,
        max_results: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[News]:
        """Collect from all social media parsers concurrently with fallback on errors"""
        logger.debug(
            "Начинаем сбор данных из социальных сетей для '%s'", company_name
        )

        tasks = []
        parser_names = []

        for name, parser in self.social_parsers.items():
            if parser.is_configured():
                logger.debug("Запускаем парсер '%s'", name)
                task = parser.parse(company_name, max_results, start_date, end_date)
                tasks.append(task)
                parser_names.append(name)
            else:
                logger.debug("Парсер '%s' не настроен, пропускаем", name)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Flatten results with detailed error tracking
        all_news = []
        successful_parsers = []
        failed_parsers = []

        for idx, result in enumerate(results):
            parser_name = parser_names[idx]

            if isinstance(result, list):
                all_news.extend(result)
                successful_parsers.append(parser_name)
                logger.debug(
                    "Парсер '%s' успешно завершён: %s материалов",
                    parser_name, len(result)
                )
            elif isinstance(result, Exception):
                failed_parsers.append(parser_name)
                logger.warning(
                    "Парсер '%s' завершился с ошибкой (fallback): %s",
                    parser_name, result
                )

        logger.info(
            "Парсеры соцсетей завершены для '%s'. Получено %s материалов "
            "(успешно: %s, ошибки: %s)",
            company_name,
            len(all_news),
            successful_parsers,
            failed_parsers
        )

        return all_news

    def get_news_from_db(
        self,
        company_name: str,
        limit: int = 100
    ) -> List[News]:
        """
        Retrieve news from database

        Args:
            company_name: Company name
            limit: Maximum results

        Returns:
            List of news from database
        """
        return self.db.get_news_by_company(company_name, limit)

    def get_stats(self, company_name: str) -> dict:
        """
        Get statistics for company news

        Args:
            company_name: Company name

        Returns:
            Dictionary with statistics
        """
        news_by_source = self.db.get_news_count_by_source(company_name)
        total = sum(news_by_source.values())

        return {
            'total_articles': total,
            'by_source': news_by_source,
            'available_sources': self.get_available_sources()
        }

    def _filter_by_period(
        self,
        news_list: List[News],
        start_date: Optional[datetime],
        end_date: Optional[datetime]
    ) -> List[News]:
        if not start_date and not end_date:
            return news_list

        def in_period(item: News) -> bool:
            reference = item.publish_date or item.collected_at
            if start_date and reference < start_date:
                return False
            if end_date and reference > end_date:
                return False
            return True

        return [item for item in news_list if in_period(item)]
