# Base Social Media Parser Class

from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import datetime, timezone

from src.models.news import News
from src.core.config import config


# Base Social Media Parser
class BaseSocialParser(ABC):
    """Abstract base class for social media parsers"""

    def __init__(self):
        self.deep_search = config.DEEP_SEARCH
        # Use larger default batch when deep search mode is enabled
        self.max_results = 50 if self.deep_search else 20

    @abstractmethod
    async def parse(self, company_name: str, max_results: Optional[int] = None) -> List[News]:
        """
        Parse social media for company mentions

        Args:
            company_name: Name of the company to search for
            max_results: Maximum number of results to return

        Returns:
            List of News objects
        """
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        """Check if the parser is properly configured"""
        pass

    def _create_news_item(
        self,
        company_name: str,
        title: str,
        content: str,
        url: str,
        source: str,
        publish_date: Optional[datetime] = None
    ) -> News:
        """
        Create News object

        Args:
            company_name: Company name
            title: Post title/author
            content: Post content
            url: Post URL
            source: Source identifier
            publish_date: Publication date (if None, uses collected_at)

        Returns:
            News object
        """
        collected_at = datetime.now(timezone.utc)

        # Ensure publish_date is timezone-aware
        if publish_date and publish_date.tzinfo is None:
            publish_date = publish_date.replace(tzinfo=timezone.utc)

        # Fallback: if no publish_date found, use collected_at
        if not publish_date:
            publish_date = collected_at

        return News(
            company_name=company_name,
            title=title,
            content=content,
            url=url,
            source=source,
            publish_date=publish_date,
            collected_at=collected_at
        )
