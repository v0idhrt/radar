
import os
from dotenv import load_dotenv
from typing import Optional

load_dotenv()


class Config:

    GOOGLE_API_KEY: Optional[str] = os.getenv("GOOGLE_API_KEY")
    GOOGLE_CX: Optional[str] = os.getenv("GOOGLE_CX")

    YANDEX_API_KEY: Optional[str] = os.getenv("YANDEX_API_KEY")
    YANDEX_FOLDER_ID: Optional[str] = os.getenv("YANDEX_FOLDER_ID")

    SERPER_API_KEY: Optional[str] = os.getenv("SERPER_API_KEY")

    TELEGRAM_API_ID: Optional[str] = os.getenv("TELEGRAM_API_ID")
    TELEGRAM_API_HASH: Optional[str] = os.getenv("TELEGRAM_API_HASH")
    TELEGRAM_PHONE: Optional[str] = os.getenv("TELEGRAM_PHONE")

    TWITTER_BEARER_TOKEN: Optional[str] = os.getenv("TWITTER_BEARER_TOKEN")
    TWITTER_API_KEY: Optional[str] = os.getenv("TWITTER_API_KEY")
    TWITTER_API_SECRET: Optional[str] = os.getenv("TWITTER_API_SECRET")

    TWITTER_ACCOUNTS: str = os.getenv(
        "TWITTER_ACCOUNTS",
        ""  
    )

    ENABLE_TWITTER: bool = os.getenv("ENABLE_TWITTER", "false").lower() in ("true", "1", "yes")

    TELEGRAM_CHANNELS: str = os.getenv(
        "TELEGRAM_CHANNELS",
        "@Reuters,@BBCNews,@CNNBrk,@Forbes,@TechCrunch,@TheEconomist,@FT,@business,@technology"
    )

    DATABASE_PATH: str = os.getenv("DATABASE_PATH", "radar_news.db")

    MAX_RESULTS_PER_SOURCE: int = int(os.getenv("MAX_RESULTS_PER_SOURCE", "50"))
    REQUEST_TIMEOUT: int = int(os.getenv("REQUEST_TIMEOUT", "30"))
    USER_AGENT: str = os.getenv(
        "USER_AGENT",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    )

    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))
    RETRY_DELAY: int = int(os.getenv("RETRY_DELAY", "2"))

    FETCH_FULL_ARTICLE_CONTENT: bool = os.getenv("FETCH_FULL_ARTICLE_CONTENT", "false").lower() in ("true", "1", "yes")

    PREFERRED_NEWS_DOMAINS: str = os.getenv(
        "PREFERRED_NEWS_DOMAINS",
        ""  
    )

    DEEP_SEARCH: bool = os.getenv("DEEP_SEARCH", "false").lower() in ("true", "1", "yes")

    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT: str = os.getenv(
        "LOG_FORMAT",
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )
    LOG_DATE_FORMAT: str = os.getenv("LOG_DATE_FORMAT", "%Y-%m-%d %H:%M:%S")

    @classmethod
    def validate_search_apis(cls) -> dict:
        """Check which search APIs are configured"""
        return {
            'google': bool(cls.GOOGLE_API_KEY and cls.GOOGLE_CX),
            'yandex': bool(cls.YANDEX_API_KEY and cls.YANDEX_FOLDER_ID),
            'serper': bool(cls.SERPER_API_KEY),
        }

    @classmethod
    def validate_social_apis(cls) -> dict:
        """Check which social media APIs are configured"""
        return {
            'telegram': bool(cls.TELEGRAM_API_ID and cls.TELEGRAM_API_HASH),
            'twitter': cls.ENABLE_TWITTER and bool(
                cls.TWITTER_BEARER_TOKEN or (cls.TWITTER_API_KEY and cls.TWITTER_API_SECRET)
            ),
        }


# Global Config Instance
config = Config()
