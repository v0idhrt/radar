"""
Оптимизированный сборщик новостей с кэшированием и асинхронной обработкой
"""

from typing import List, Optional
from datetime import datetime, timedelta
import hashlib
import json

from src.models.news import News
from src.core.database import Database
from src.services.aggregator import NewsAggregator
from src.services.logging_service import get_logger

logger = get_logger(__name__)


class NewsCollectorService:
    """Сервис для сбора новостей с кэшированием"""
    
    def __init__(self, db: Optional[Database] = None):
        self.db = db if db is not None else Database()
        self.aggregator = NewsAggregator(db=self.db)
        self._cache: dict = {}  # Простой кэш в памяти
        self._cache_ttl = 300  # 5 минут
    
    def _get_cache_key(self, company_name: str, params: dict) -> str:
        """Генерация ключа кэша"""
        key_data = f"{company_name}:{json.dumps(params, sort_keys=True)}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def _is_cache_valid(self, cache_entry: dict) -> bool:
        """Проверка валидности кэша"""
        if not cache_entry:
            return False
        
        cached_time = cache_entry.get('timestamp', 0)
        current_time = datetime.now().timestamp()
        return (current_time - cached_time) < self._cache_ttl
    
    async def collect_news_with_cache(
        self,
        company_name: str,
        max_results_per_source: int = 30,
        use_search: bool = True,
        use_social: bool = False,
        save_to_db: bool = True,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[News]:
        """Сбор новостей с использованием кэша"""
        
        # Создаем ключ кэша
        cache_params = {
            'max_results': max_results_per_source,
            'use_search': use_search,
            'use_social': use_social,
            'start_date': start_date.isoformat() if start_date else None,
            'end_date': end_date.isoformat() if end_date else None,
        }
        cache_key = self._get_cache_key(company_name, cache_params)
        
        # Проверяем кэш
        if cache_key in self._cache and self._is_cache_valid(self._cache[cache_key]):
            logger.info(f"Возврат из кэша для '{company_name}'")
            return self._cache[cache_key]['data']
        
        # Собираем новости
        logger.info(f"Сбор новостей для '{company_name}' (кэш промах)")
        news_items = await self.aggregator.collect_news(
            company_name=company_name,
            max_results_per_source=max_results_per_source,
            use_search=use_search,
            use_social=use_social,
            save_to_db=save_to_db,
            start_date=start_date,
            end_date=end_date
        )
        
        # Сохраняем в кэш
        self._cache[cache_key] = {
            'timestamp': datetime.now().timestamp(),
            'data': news_items
        }
        
        # Очистка старых записей кэша (простая стратегия)
        self._cleanup_cache()
        
        return news_items
    
    def _cleanup_cache(self):
        """Очистка устаревших записей кэша"""
        current_time = datetime.now().timestamp()
        expired_keys = [
            key for key, value in self._cache.items()
            if (current_time - value.get('timestamp', 0)) > self._cache_ttl
        ]
        
        for key in expired_keys:
            del self._cache[key]
        
        if expired_keys:
            logger.debug(f"Очищено {len(expired_keys)} устаревших записей кэша")
    
    def clear_cache(self):
        """Полная очистка кэша"""
        self._cache.clear()
        logger.info("Кэш очищен")
    
    def get_cache_stats(self) -> dict:
        """Статистика кэша"""
        valid_entries = sum(
            1 for entry in self._cache.values()
            if self._is_cache_valid(entry)
        )
        
        return {
            'total_entries': len(self._cache),
            'valid_entries': valid_entries,
            'ttl_seconds': self._cache_ttl
        }