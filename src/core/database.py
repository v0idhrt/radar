
import sqlite3
from contextlib import contextmanager
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import json

from src.models.news import News, Company, Source
from src.core.database_pool import get_db_connection as get_pooled_connection
from src.services.logging_service import get_logger


DB_PATH = "radar_news.db"


logger = get_logger(__name__)


@contextmanager
def get_db_connection():
    """Использует connection pool вместо прямого подключения"""
    with get_pooled_connection(DB_PATH) as conn:
        yield conn


class Database:

    @staticmethod
    def init_db():
        with get_db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS companies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL,
                    last_searched TEXT
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sources (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    type TEXT NOT NULL,
                    enabled INTEGER DEFAULT 1,
                    last_used TEXT
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS news (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    company_name TEXT NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT,
                    url TEXT NOT NULL,
                    source TEXT NOT NULL,
                    publish_date TEXT,
                    collected_at TEXT NOT NULL,
                    relevance_score REAL,
                    dedup_group TEXT,
                    UNIQUE(url, company_name)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS stock_tickers (
                    ticker TEXT PRIMARY KEY,
                    company_name TEXT NOT NULL,
                    exchange TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS anomalies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT NOT NULL,
                    company_name TEXT NOT NULL,
                    z_score REAL NOT NULL,
                    delta REAL NOT NULL,
                    direction TEXT NOT NULL,
                    price REAL NOT NULL,
                    timestamp TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    news_collected INTEGER DEFAULT 0,
                    news_count INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL
                )
            """)

            # Create indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_news_company ON news(company_name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_news_source ON news(source)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_news_publish_date ON news(publish_date)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_news_url ON news(url)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_news_dedup_group ON news(dedup_group)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tickers_company ON stock_tickers(company_name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tickers_exchange ON stock_tickers(exchange)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_anomalies_ticker ON anomalies(ticker)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_anomalies_timestamp ON anomalies(timestamp)")

    @staticmethod
    def add_company(company: Company) -> int:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO companies (name, created_at) VALUES (?, ?)",
                (company.name, company.created_at.isoformat())
            )
            return cursor.lastrowid

    @staticmethod
    def get_company(name: str) -> Optional[Company]:
        """Get company by name"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            row = cursor.execute("SELECT * FROM companies WHERE name = ?", (name,)).fetchone()
            if row:
                return Company(
                    id=row['id'],
                    name=row['name'],
                    created_at=datetime.fromisoformat(row['created_at']).replace(tzinfo=timezone.utc),
                    last_searched=datetime.fromisoformat(row['last_searched']).replace(tzinfo=timezone.utc) if row['last_searched'] else None
                )
        return None

    @staticmethod
    def update_company_last_searched(name: str):
        """Update last searched timestamp for company"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE companies SET last_searched = ? WHERE name = ?",
                (datetime.now(timezone.utc).isoformat(), name)
            )

    # News Operations
    @staticmethod
    def add_news(news: News) -> Optional[int]:
        """Add news to database, returns id or None if duplicate"""
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR IGNORE INTO news (company_name, title, content, url, source,
                                     publish_date, collected_at, relevance_score, dedup_group)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    news.company_name,
                    news.title,
                    news.content,
                    news.url,
                    news.source,
                    news.publish_date.isoformat() if news.publish_date else None,
                    news.collected_at.isoformat(),
                    news.relevance_score,
                    news.dedup_group
                ))
                # Если строка не была вставлена (дубликат), lastrowid будет 0
                inserted_id = cursor.lastrowid
                if inserted_id == 0:
                    # Дубликат - логируем и возвращаем None
                    logger.debug(f"Duplicate news skipped: {news.url} for {news.company_name}")
                    return None
                return inserted_id
        except sqlite3.IntegrityError as e:
            # На всякий случай оставляем обработку IntegrityError
            logger.warning(f"IntegrityError when adding news (should not happen with OR IGNORE): {e}")
            return None

    @staticmethod
    def get_news_by_company(company_name: str, limit: int = 100) -> List[News]:
        """Get all news for a company"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            rows = cursor.execute("""
                SELECT * FROM news WHERE company_name = ?
                ORDER BY publish_date DESC, collected_at DESC
                LIMIT ?
            """, (company_name, limit)).fetchall()

            return [
                News(
                    id=row['id'],
                    company_name=row['company_name'],
                    title=row['title'],
                    content=row['content'],
                    url=row['url'],
                    source=row['source'],
                    publish_date=datetime.fromisoformat(row['publish_date']).replace(tzinfo=timezone.utc) if row['publish_date'] else None,
                    collected_at=datetime.fromisoformat(row['collected_at']).replace(tzinfo=timezone.utc),
                    relevance_score=row['relevance_score'],
                    dedup_group=row['dedup_group']
                )
                for row in rows
            ]

    @staticmethod
    def get_news_by_company_and_period(
        company_name: str,
        start: Optional[datetime],
        end: Optional[datetime],
        limit: int = 500
    ) -> List[News]:
        """Retrieve news for company within time window (publish_date fallback to collected_at)."""
        with get_db_connection() as conn:
            cursor = conn.cursor()

            base_query = [
                "SELECT * FROM news",
                "WHERE company_name = ?"
            ]
            params: List[Any] = [company_name]

            if start:
                base_query.append("AND COALESCE(publish_date, collected_at) >= ?")
                params.append(start.isoformat())

            if end:
                base_query.append("AND COALESCE(publish_date, collected_at) <= ?")
                params.append(end.isoformat())

            base_query.append("ORDER BY publish_date DESC, collected_at DESC LIMIT ?")
            params.append(limit)

            rows = cursor.execute(" ".join(base_query), params).fetchall()

            return [
                News(
                    id=row['id'],
                    company_name=row['company_name'],
                    title=row['title'],
                    content=row['content'],
                    url=row['url'],
                    source=row['source'],
                    publish_date=datetime.fromisoformat(row['publish_date']).replace(tzinfo=timezone.utc) if row['publish_date'] else None,
                    collected_at=datetime.fromisoformat(row['collected_at']).replace(tzinfo=timezone.utc),
                    relevance_score=row['relevance_score'],
                    dedup_group=row['dedup_group']
                )
                for row in rows
            ]

    @staticmethod
    def check_url_exists(url: str, company_name: str) -> bool:
        """Check if URL already exists for company"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            result = cursor.execute(
                "SELECT 1 FROM news WHERE url = ? AND company_name = ?",
                (url, company_name)
            ).fetchone()
            return result is not None

    @staticmethod
    def get_news_count_by_source(company_name: str) -> Dict[str, int]:
        """Get news count grouped by source"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            rows = cursor.execute("""
                SELECT source, COUNT(*) as count
                FROM news
                WHERE company_name = ?
                GROUP BY source
            """, (company_name,)).fetchall()

            return {row['source']: row['count'] for row in rows}

    # Source Operations
    @staticmethod
    def add_source(source: Source) -> int:
        """Add source to database"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO sources (name, type, enabled)
                VALUES (?, ?, ?)
            """, (source.name, source.type, source.enabled))
            return cursor.lastrowid

    @staticmethod
    def get_enabled_sources() -> List[Source]:
        """Get all enabled sources"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            rows = cursor.execute("SELECT * FROM sources WHERE enabled = 1").fetchall()

            return [
                Source(
                    id=row['id'],
                    name=row['name'],
                    type=row['type'],
                    enabled=bool(row['enabled']),
                    last_used=datetime.fromisoformat(row['last_used']).replace(tzinfo=timezone.utc) if row['last_used'] else None
                )
                for row in rows
            ]

    # Ticker Operations
    @staticmethod
    def add_ticker(ticker: str, company_name: str, exchange: str) -> bool:
        """Add stock ticker mapping"""
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO stock_tickers (ticker, company_name, exchange, created_at)
                    VALUES (?, ?, ?, ?)
                """, (ticker, company_name, exchange, datetime.now(timezone.utc).isoformat()))
                return True
        except Exception:
            return False

    @staticmethod
    def get_company_by_ticker(ticker: str) -> Optional[str]:
        """Get company name by ticker"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            row = cursor.execute(
                "SELECT company_name FROM stock_tickers WHERE ticker = ?",
                (ticker,)
            ).fetchone()
            return row['company_name'] if row else None

    @staticmethod
    def get_ticker_by_company(company_name: str) -> Optional[str]:
        """Get ticker by company name"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            row = cursor.execute(
                "SELECT ticker FROM stock_tickers WHERE company_name = ?",
                (company_name,)
            ).fetchone()
            return row['ticker'] if row else None

    @staticmethod
    def get_all_tickers() -> List[Dict[str, str]]:
        """Get all stock tickers"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            rows = cursor.execute("SELECT ticker, company_name, exchange FROM stock_tickers").fetchall()
            return [
                {
                    'ticker': row['ticker'],
                    'company_name': row['company_name'],
                    'exchange': row['exchange']
                }
                for row in rows
            ]

    # Anomaly Operations
    @staticmethod
    def add_anomaly(ticker: str, company_name: str, z_score: float, delta: float,
                    direction: str, price: float, timestamp: str, timeframe: str,
                    news_count: int) -> int:
        """Add anomaly record"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO anomalies (ticker, company_name, z_score, delta, direction,
                                      price, timestamp, timeframe, news_collected, news_count, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
            """, (ticker, company_name, z_score, delta, direction, price, timestamp,
                  timeframe, news_count, datetime.now(timezone.utc).isoformat()))
            return cursor.lastrowid

    @staticmethod
    def get_recent_anomalies(limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent anomalies"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            rows = cursor.execute("""
                SELECT * FROM anomalies
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,)).fetchall()

            return [dict(row) for row in rows]

    @staticmethod
    def get_impactful_anomalies(limit: int = 10) -> List[Dict[str, Any]]:
        """Get anomalies with news (impactful events)"""
        with get_db_connection() as conn:
            cursor = conn.cursor()

            fetch_limit = max(limit * 3, limit)
            rows = cursor.execute("""
                SELECT a.*
                FROM anomalies a
                WHERE EXISTS (
                    SELECT 1 FROM news n
                    WHERE n.company_name = a.company_name
                )
                ORDER BY a.created_at DESC
                LIMIT ?
            """, (fetch_limit,)).fetchall()

            unique_by_company: Dict[str, Dict[str, Any]] = {}
            for row in rows:
                company_key = row['company_name'] or row['ticker']
                if company_key not in unique_by_company:
                    unique_by_company[company_key] = dict(row)

            # Sort by absolute z-score, then by created_at desc
            sorted_rows = sorted(
                unique_by_company.values(),
                key=lambda item: (abs(item.get('z_score', 0)), item.get('created_at')),
                reverse=True
            )

            return sorted_rows[:limit]

    @staticmethod
    def get_hot_news(hours: int = 24, limit: int = 50) -> List[News]:
        """
        Получить "горячие новости" - свежие новости, связанные со значимыми аномалиями рынка
        
        Args:
            hours: Количество часов назад для поиска новостей (по умолчанию 24)
            limit: Максимальное количество новостей
            
        Returns:
            Список горячих новостей, отсортированных по важности (z_score) и времени
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Рассчитываем временную метку для фильтрации
            from datetime import timedelta
            cutoff_time = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
            
            # Получаем новости, связанные с недавними значимыми аномалиями
            rows = cursor.execute("""
                SELECT DISTINCT n.*, a.z_score, a.delta, a.direction, a.timestamp as anomaly_timestamp
                FROM news n
                INNER JOIN anomalies a ON n.company_name = a.company_name
                WHERE a.created_at >= ?
                    AND a.news_collected = 1
                    AND COALESCE(n.publish_date, n.collected_at) >= ?
                ORDER BY ABS(a.z_score) DESC, n.publish_date DESC, n.collected_at DESC
                LIMIT ?
            """, (cutoff_time, cutoff_time, limit)).fetchall()
            
            return [
                News(
                    id=row['id'],
                    company_name=row['company_name'],
                    title=row['title'],
                    content=row['content'],
                    url=row['url'],
                    source=row['source'],
                    publish_date=datetime.fromisoformat(row['publish_date']).replace(tzinfo=timezone.utc) if row['publish_date'] else None,
                    collected_at=datetime.fromisoformat(row['collected_at']).replace(tzinfo=timezone.utc),
                    relevance_score=row['relevance_score'],
                    dedup_group=row['dedup_group']
                )
                for row in rows
            ]
