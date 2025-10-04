"""
Оптимизированный Database Manager с Connection Pool и WAL режимом
"""

import sqlite3
from contextlib import contextmanager
from queue import Queue, Empty
from threading import Lock
from typing import Optional, Generator
from datetime import datetime, timezone

from src.services.logging_service import get_logger

logger = get_logger(__name__)


class DatabasePool:
    """Connection Pool для SQLite с поддержкой WAL режима"""
    
    def __init__(self, db_path: str, pool_size: int = 10, timeout: float = 30.0):
        self.db_path = db_path
        self.pool_size = pool_size
        self.timeout = timeout
        self._pool: Queue = Queue(maxsize=pool_size)
        self._lock = Lock()
        self._initialized = False
        
        # Инициализация пула
        self._initialize_pool()
        
    def _initialize_pool(self):
        """Инициализация connection pool"""
        if self._initialized:
            return
            
        with self._lock:
            if self._initialized:
                return
                
            logger.info(f"Инициализация connection pool: {self.pool_size} соединений")
            
            # Создаем пул соединений
            for _ in range(self.pool_size):
                conn = self._create_connection()
                self._pool.put(conn)
            
            self._initialized = True
            logger.info("Connection pool инициализирован")
    
    def _create_connection(self) -> sqlite3.Connection:
        """Создание нового соединения с оптимальными настройками"""
        conn = sqlite3.connect(
            self.db_path,
            timeout=self.timeout,
            check_same_thread=False,  # Разрешить использование в разных потоках
            isolation_level=None  # Autocommit mode для WAL
        )
        conn.row_factory = sqlite3.Row
        
        # Включаем WAL режим для лучшей конкурентности
        conn.execute("PRAGMA journal_mode=WAL")
        
        # Оптимизация производительности
        conn.execute("PRAGMA synchronous=NORMAL")  # Баланс между безопасностью и скоростью
        conn.execute("PRAGMA cache_size=-64000")  # 64MB cache
        conn.execute("PRAGMA temp_store=MEMORY")
        conn.execute("PRAGMA mmap_size=268435456")  # 256MB memory-mapped I/O
        
        return conn
    
    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Получение соединения из пула"""
        conn = None
        try:
            # Получаем соединение из пула
            try:
                conn = self._pool.get(timeout=5.0)
            except Empty:
                logger.warning("Pool exhausted, creating temporary connection")
                conn = self._create_connection()
                
            yield conn
            
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Database error: {e}", exc_info=True)
            raise
        finally:
            if conn:
                try:
                    # Возвращаем соединение в пул (если не временное)
                    self._pool.put_nowait(conn)
                except:
                    # Если пул полон, закрываем временное соединение
                    conn.close()
    
    def close_all(self):
        """Закрытие всех соединений в пуле"""
        logger.info("Закрытие connection pool")
        while not self._pool.empty():
            try:
                conn = self._pool.get_nowait()
                conn.close()
            except Empty:
                break
        logger.info("Connection pool закрыт")


# Глобальный пул соединений
_db_pool: Optional[DatabasePool] = None
_pool_lock = Lock()


def get_db_pool(db_path: str = "radar_news.db", pool_size: int = 10) -> DatabasePool:
    """Получение глобального пула соединений (singleton)"""
    global _db_pool
    
    if _db_pool is None:
        with _pool_lock:
            if _db_pool is None:
                _db_pool = DatabasePool(db_path, pool_size)
    
    return _db_pool


@contextmanager
def get_db_connection(db_path: str = "radar_news.db"):
    """Context manager для получения соединения из пула"""
    pool = get_db_pool(db_path)
    with pool.get_connection() as conn:
        yield conn