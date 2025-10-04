
import sqlite3
from contextlib import contextmanager
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import json

from src.models.news import News, Company, Source


DB_PATH = "radar_news.db"


@contextmanager
def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


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

            # Create indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_news_company ON news(company_name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_news_source ON news(source)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_news_publish_date ON news(publish_date)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_news_url ON news(url)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_news_dedup_group ON news(dedup_group)")

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
                    INSERT INTO news (company_name, title, content, url, source,
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
                return cursor.lastrowid
        except sqlite3.IntegrityError:
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
