# Telegram Channels Parser Service

from typing import List, Optional
from datetime import datetime, timedelta, timezone
import asyncio
import re

from src.services.social.base import BaseSocialParser
from src.models.news import News
from src.core.config import config
from ..logging_service import get_logger

logger = get_logger(__name__)


# Telegram Parser
class TelegramParser(BaseSocialParser):
    """Telegram channels parser using Telethon"""

    def __init__(self):
        super().__init__()
        self.api_id = config.TELEGRAM_API_ID
        self.api_hash = config.TELEGRAM_API_HASH
        self.phone = config.TELEGRAM_PHONE

    def is_configured(self) -> bool:
        """Check if Telegram parser is configured"""
        return bool(self.api_id and self.api_hash)

    async def parse(
        self,
        company_name: str,
        max_results: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[News]:
        """
        Parse Telegram channels for company mentions (parallel processing)

        Args:
            company_name: Company name to search
            max_results: Maximum results to return
            start_date: Optional start date for search results
            end_date: Optional end date for search results

        Returns:
            List of News objects
        """
        if not self.is_configured():
            logger.warning("Telegram парсер не настроен, пропускаем")
            return []

        max_results = max_results or self.max_results
        news_items = []

        logger.info(
            "Парсинг Telegram для '%s' (max_results=%s, start_date=%s, end_date=%s)",
            company_name,
            max_results,
            start_date,
            end_date
        )

        if self.deep_search:
            logger.debug("Глубокий режим поиска включён для Telegram")

        try:
            from telethon import TelegramClient

            # Create client
            client = TelegramClient('radar_session', self.api_id, self.api_hash)

            await client.start()
            logger.debug("Telegram клиент запущен")

            # Get channels from config
            channels_str = config.TELEGRAM_CHANNELS
            channels = [ch.strip() for ch in channels_str.split(',') if ch.strip()]
            logger.debug("Каналы для парсинга: %s", channels)

            # Parse all channels in parallel
            tasks = [
                self._parse_channel(client, channel_username, company_name, start_date, end_date)
                for channel_username in channels
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Collect results from all channels
            for result in results:
                if isinstance(result, list):
                    news_items.extend(result)
                    if len(news_items) >= max_results:
                        break
                elif isinstance(result, Exception):
                    logger.error("Ошибка при парсинге канала: %s", result, exc_info=result)

            # Limit to max_results
            news_items = news_items[:max_results]

            await client.disconnect()
            logger.debug("Telegram клиент отключён")

        except ImportError:
            logger.warning("Telethon не установлен, Telegram парсер недоступен")
        except Exception as e:
            logger.error("Ошибка парсинга Telegram: %s", e, exc_info=e)

        logger.info(
            "Telegram парсинг завершён для '%s'. Найдено %s материалов",
            company_name,
            len(news_items),
        )

        return news_items

    async def _parse_channel(
        self,
        client,
        channel_username: str,
        company_name: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[News]:
        """
        Parse single channel (helper for parallel processing)

        Args:
            client: Telegram client instance
            channel_username: Channel username to parse
            company_name: Company name to search
            start_date: Optional start date for filtering
            end_date: Optional end date for filtering

        Returns:
            List of News objects from this channel
        """
        news_items = []

        try:
            logger.debug("Чтение канала %s", channel_username)

            # Get channel entity
            channel = await client.get_entity(channel_username)
            channel_title = getattr(channel, 'title', channel_username.lstrip('@'))

            # Calculate offset_date: use start_date if provided, otherwise last 7 or 30 days in deep mode
            if start_date:
                offset_date = start_date
            else:
                lookback_days = 30 if self.deep_search else 7
                offset_date = datetime.now(timezone.utc) - timedelta(days=lookback_days)

            # Increased limit to get more messages when deep search enabled
            messages_limit = 1000 if self.deep_search else 500
            messages = await client.get_messages(
                channel,
                limit=messages_limit,
                offset_date=offset_date
            )
            logger.debug(
                "Получено %s сообщений из %s", len(messages), channel_username
            )

            # Prepare search variations for better matching
            search_variations = self._prepare_search_variations(company_name)

            # Filter messages mentioning company
            for msg in messages:
                if not msg.text:
                    continue

                segments = self._split_message_segments(msg.text)
                for idx, segment in enumerate(segments):
                    cleaned_segment = self._clean_message_text(segment)
                    if not cleaned_segment:
                        continue

                    if not self._message_contains_company(cleaned_segment, search_variations):
                        continue

                    title = self._build_title(channel_title, cleaned_segment)
                    url_suffix = '' if idx == 0 else f"?part={idx+1}"
                    news_item = self._create_news_item(
                        company_name=company_name,
                        title=title,
                        content=cleaned_segment,
                        url=f"https://t.me/{channel_username.replace('@', '')}/{msg.id}{url_suffix}",
                        source=f"telegram:{channel_username.replace('@', '')}",
                        publish_date=msg.date
                    )
                    news_items.append(news_item)

        except Exception as e:
            logger.error(
                "Ошибка обработки канала %s: %s", channel_username, e, exc_info=e
            )

        return news_items

    def _prepare_search_variations(self, company_name: str) -> List[str]:
        """
        Prepare search variations for better matching in messages

        Args:
            company_name: Original company name

        Returns:
            List of search variations
        """
        variations = [
            company_name.lower(),
            company_name.upper(),
            company_name.title(),
            company_name,
        ]

        # Add variations with quotes
        variations.extend([
            f'"{company_name}"',
            f'«{company_name}»',
        ])

        # Add hashtag variation and compact forms for better matching
        hashtag = company_name.replace(' ', '').replace('-', '')
        variations.append(f'#{hashtag}'.lower())
        variations.append(hashtag.lower())

        if self.deep_search:
            # When deep search is enabled, also look for key abbreviations
            initials = ''.join(word[0] for word in company_name.split() if word)
            if initials:
                variations.append(initials.lower())

        # Remove duplicates
        return list(set(variations))

    def _message_contains_company(self, text: str, search_variations: List[str]) -> bool:
        """
        Check if message contains company name in any variation
        Searches in the entire message, including large texts

        Args:
            text: Message text
            search_variations: List of company name variations to search

        Returns:
            True if any variation found
        """
        # Search in full text
        text_lower = text.lower()

        for variation in search_variations:
            if variation.lower() in text_lower:
                return True

        # Split into paragraphs for better search in large messages
        paragraphs = text.split('\n')
        for paragraph in paragraphs:
            paragraph_lower = paragraph.lower()
            for variation in search_variations:
                if variation.lower() in paragraph_lower:
                    return True

        return False

    def _split_message_segments(self, text: str) -> List[str]:
        """Split long telegram message into logical segments."""
        if not text:
            return []

        splitter = re.compile(r"(?:Please open Telegram to view this post\s*VIEW IN TELEGRAM)+", re.IGNORECASE)
        parts = [part.strip() for part in splitter.split(text) if part.strip()]
        if parts:
            return parts
        return [text]

    def _clean_message_text(self, text: str) -> str:
        """Normalize telegram message content by removing service phrases and noise."""
        if not text:
            return ''

        lines = []
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            lowered = line.lower()
            if 'please open telegram to view this post' in lowered:
                continue
            if 'view in telegram' in lowered:
                continue
            if lowered.startswith('read more on telegram'):
                continue

            if re.fullmatch(r"[\d\s:+\-.,❤🔥👍🥰👏🤝⚡💯🕊😎🫡🙏💋🎄🍾🦄😇🐳💔🆒🤝🪄🍀\u263a-\U0001FAFF]+", line):
                continue

            if line not in lines:
                lines.append(line)

        return '\n'.join(lines).strip()

    def _build_title(self, channel_title: str, content: str) -> str:
        """Create human-readable title for telegram post."""
        snippet = content.replace('\n', ' ').strip()
        if len(snippet) > 120:
            snippet = snippet[:117].rstrip() + '...'
        return f"{channel_title}: {snippet}"

    async def parse_specific_channels(
        self,
        company_name: str,
        channel_list: List[str],
        max_results: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[News]:
        """
        Parse specific Telegram channels (parallel processing)

        Args:
            company_name: Company name to search
            channel_list: List of channel usernames
            max_results: Maximum results to return

        Returns:
            List of News objects
        """
        if not self.is_configured():
            logger.warning("Telegram парсер не настроен для выборочных каналов")
            return []

        max_results = max_results or self.max_results
        news_items = []

        logger.info(
            "Парсинг выбранных каналов Telegram для '%s' (каналы=%s, max_results=%s)",
            company_name,
            channel_list,
            max_results,
        )

        try:
            from telethon import TelegramClient

            client = TelegramClient('radar_session', self.api_id, self.api_hash)
            await client.start()

            # Parse all channels in parallel
            tasks = [
                self._parse_channel(client, channel_username, company_name, start_date, end_date)
                for channel_username in channel_list
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Collect results from all channels
            for result in results:
                if isinstance(result, list):
                    news_items.extend(result)
                elif isinstance(result, Exception):
                    logger.error("Ошибка при парсинге канала: %s", result, exc_info=result)

            # Limit to max_results
            news_items = news_items[:max_results]

            await client.disconnect()

        except Exception as e:
            logger.error("Ошибка Telegram: %s", e, exc_info=e)

        logger.info(
            "Парсинг выбранных каналов завершён для '%s'. Найдено %s материалов",
            company_name,
            len(news_items),
        )

        return news_items
