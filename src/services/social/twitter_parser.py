# Twitter/X Parser Service

from typing import List, Optional
from datetime import datetime, timezone
import asyncio

from src.services.social.base import BaseSocialParser
from src.models.news import News
from src.core.config import config
from ..logging_service import get_logger


logger = get_logger(__name__)


# Twitter Parser
class TwitterParser(BaseSocialParser):
    """Twitter/X posts parser using tweepy API"""

    def __init__(self):
        super().__init__()
        self.bearer_token = config.TWITTER_BEARER_TOKEN
        self.twitter_accounts = self._parse_accounts(config.TWITTER_ACCOUNTS)
        self.enabled = config.ENABLE_TWITTER

    def is_configured(self) -> bool:
        """Check if Twitter parser is configured"""
        return self.enabled and bool(self.bearer_token)

    def _parse_accounts(self, accounts_str: str) -> List[str]:
        """
        Parse comma-separated accounts string into list

        Args:
            accounts_str: Comma-separated accounts

        Returns:
            List of account handles
        """
        if not accounts_str or not accounts_str.strip():
            return []

        accounts = [acc.strip().lstrip('@') for acc in accounts_str.split(',') if acc.strip()]
        return accounts

    async def parse(
        self,
        company_name: str,
        max_results: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[News]:
        """
        Parse Twitter for company mentions using tweepy API
        If TWITTER_ACCOUNTS is configured, searches only from those accounts

        Args:
            company_name: Company name to search
            max_results: Maximum results to return
            start_date: Optional start date for search results
            end_date: Optional end date for search results

        Returns:
            List of News objects
        """
        if not self.is_configured():
            logger.warning("Twitter парсер не настроен, пропускаем")
            return []

        max_results = max_results or self.max_results
        news_items = []

        logger.info(
            "Парсинг Twitter для '%s' (max_results=%s, accounts=%s)",
            company_name,
            max_results,
            self.twitter_accounts if self.twitter_accounts else "все"
        )

        if self.deep_search:
            logger.debug("Глубокий режим поиска включён для Twitter")

        try:
            import tweepy

            client = tweepy.Client(bearer_token=self.bearer_token)

            # If specific accounts configured, parse them in parallel
            if self.twitter_accounts:
                tasks = [
                    self._parse_account(client, account, company_name, max_results, start_date, end_date)
                    for account in self.twitter_accounts
                ]

                results = await asyncio.gather(*tasks, return_exceptions=True)

                for result in results:
                    if isinstance(result, list):
                        news_items.extend(result)
                        if len(news_items) >= max_results:
                            break
                    elif isinstance(result, Exception):
                        logger.error("Ошибка при парсинге аккаунта: %s", result, exc_info=result)

                # Limit to max_results
                news_items = news_items[:max_results]
            else:
                queries = self._build_global_queries(company_name)
                seen_ids = set()

                for query in queries:
                    logger.debug("Запрос tweepy (общий поиск): %s", query)
                    pagination_token = None

                    while len(news_items) < max_results:
                        page_size = min(100, max(10, max_results - len(news_items)))
                        search_params = {
                            'query': query,
                            'max_results': page_size,
                            'tweet_fields': ['created_at', 'author_id', 'text']
                        }

                        if start_date:
                            search_params['start_time'] = start_date.isoformat()
                        if end_date:
                            search_params['end_time'] = end_date.isoformat()
                        if pagination_token:
                            search_params['next_token'] = pagination_token

                        response = client.search_recent_tweets(**search_params)

                        if not response.data:
                            break

                        for tweet in response.data:
                            if tweet.id in seen_ids:
                                continue

                            publish_date = tweet.created_at
                            if publish_date and publish_date.tzinfo is None:
                                publish_date = publish_date.replace(tzinfo=timezone.utc)

                            news_item = self._create_news_item(
                                company_name=company_name,
                                title=f"Tweet {tweet.id}",
                                content=tweet.text,
                                url=f"https://twitter.com/i/web/status/{tweet.id}",
                                source='twitter',
                                publish_date=publish_date
                            )
                            news_items.append(news_item)
                            seen_ids.add(tweet.id)

                            if len(news_items) >= max_results:
                                break

                        meta = getattr(response, 'meta', None)
                        pagination_token = None

                        if meta:
                            pagination_token = meta.get('next_token') if isinstance(meta, dict) else getattr(meta, 'get', lambda *_: None)('next_token')

                        if not pagination_token or not self.deep_search:
                            break

        except Exception as e:
            logger.error("Ошибка Twitter парсинга: %s", e, exc_info=e)

        logger.info(
            "Twitter парсинг завершён для '%s'. Найдено %s материалов",
            company_name,
            len(news_items),
        )

        return news_items

    async def _parse_account(
        self,
        client,
        account: str,
        company_name: str,
        max_results: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[News]:
        """
        Parse single Twitter account for company mentions

        Args:
            client: Tweepy client instance
            account: Twitter account handle (without @)
            company_name: Company name to search
            start_date: Optional start date
            end_date: Optional end date

        Returns:
            List of News objects from this account
        """
        news_items = []

        try:
            logger.debug("Чтение аккаунта @%s", account)

            queries = self._build_account_queries(account, company_name)

            for query in queries:
                logger.debug("Запрос tweepy для @%s: %s", account, query)
                pagination_token = None

                while len(news_items) < max_results:
                    page_size = min(100, max(10, max_results - len(news_items)))
                    search_params = {
                        'query': query,
                        'max_results': page_size,
                        'tweet_fields': ['created_at', 'author_id', 'text']
                    }

                    if start_date:
                        search_params['start_time'] = start_date.isoformat()
                    if end_date:
                        search_params['end_time'] = end_date.isoformat()
                    if pagination_token:
                        search_params['next_token'] = pagination_token

                    response = client.search_recent_tweets(**search_params)

                    if not response.data:
                        break

                    logger.debug("Получено %s твитов из @%s", len(response.data), account)

                    for tweet in response.data:
                        publish_date = tweet.created_at
                        if publish_date and publish_date.tzinfo is None:
                            publish_date = publish_date.replace(tzinfo=timezone.utc)

                        news_item = self._create_news_item(
                            company_name=company_name,
                            title=f"@{account} - {tweet.created_at.strftime('%Y-%m-%d')}",
                            content=tweet.text,
                            url=f"https://twitter.com/{account}/status/{tweet.id}",
                            source='twitter',
                            publish_date=publish_date
                        )
                        news_items.append(news_item)

                        if len(news_items) >= max_results:
                            break

                    meta = getattr(response, 'meta', None)
                    pagination_token = None
                    if meta:
                        pagination_token = meta.get('next_token') if isinstance(meta, dict) else getattr(meta, 'get', lambda *_: None)('next_token')

                    if not pagination_token or not self.deep_search:
                        break

        except Exception as e:
            logger.error("Ошибка обработки @%s: %s", account, e, exc_info=e)

        return news_items

    def _build_global_queries(self, company_name: str) -> List[str]:
        """Build global search query variations for Twitter search."""
        queries = [f'{company_name} -is:retweet lang:ru']

        if self.deep_search:
            queries.extend([
                f'"{company_name}" -is:retweet',
                f'{company_name} -is:retweet lang:en',
                f'{company_name} новости -is:retweet lang:ru',
            ])

        # Preserve order while removing duplicates
        seen = set()
        unique_queries = []
        for query in queries:
            if query not in seen:
                unique_queries.append(query)
                seen.add(query)
        return unique_queries

    def _build_account_queries(self, account: str, company_name: str) -> List[str]:
        """Build account specific query variations."""
        queries = [f'from:{account} {company_name} -is:retweet']

        if self.deep_search:
            queries.extend([
                f'from:{account} "{company_name}" -is:retweet',
                f'from:{account} {company_name} -is:retweet lang:en',
            ])

        seen = set()
        unique_queries = []
        for query in queries:
            if query not in seen:
                unique_queries.append(query)
                seen.add(query)
        return unique_queries
