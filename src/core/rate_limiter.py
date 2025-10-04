"""
Rate Limiter для контроля частоты запросов к внешним API
Предотвращает Too Many Requests ошибки
"""

import time
from typing import Dict, Optional
from collections import deque
from datetime import datetime, timedelta
import asyncio

from src.services.logging_service import get_logger

logger = get_logger(__name__)


class RateLimiter:
    """Rate limiter с sliding window алгоритмом"""
    
    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: deque = deque()
        self._lock = asyncio.Lock()
    
    async def acquire(self, wait: bool = True) -> bool:
        """
        Попытка получить разрешение на запрос
        
        Args:
            wait: Ждать ли, если лимит исчерпан
            
        Returns:
            True если разрешено, False если лимит исчерпан (при wait=False)
        """
        async with self._lock:
            now = time.time()
            window_start = now - self.window_seconds
            
            # Удаляем старые запросы
            while self._requests and self._requests[0] < window_start:
                self._requests.popleft()
            
            # Проверяем лимит
            if len(self._requests) < self.max_requests:
                self._requests.append(now)
                return True
            
            if not wait:
                return False
            
            # Ждём до момента, когда можно будет сделать запрос
            sleep_time = self._requests[0] + self.window_seconds - now + 0.1
            if sleep_time > 0:
                logger.debug(f"Rate limit reached, waiting {sleep_time:.1f}s")
                await asyncio.sleep(sleep_time)
                return await self.acquire(wait=False)
            
            return False
    
    def get_stats(self) -> Dict:
        """Получить статистику"""
        now = time.time()
        window_start = now - self.window_seconds
        
        # Подсчитать активные запросы
        active_requests = sum(1 for req in self._requests if req >= window_start)
        
        return {
            "max_requests": self.max_requests,
            "window_seconds": self.window_seconds,
            "current_requests": active_requests,
            "remaining": max(0, self.max_requests - active_requests),
            "available_in": (self._requests[0] + self.window_seconds - now) if self._requests else 0
        }


class APIRateLimiters:
    """Менеджер rate limiter'ов для разных API"""
    
    def __init__(self):
        self._limiters: Dict[str, RateLimiter] = {}
        
        # Настройка лимитов для разных API
        self._limiters['google'] = RateLimiter(max_requests=100, window_seconds=60)  # 100 req/min
        self._limiters['serper'] = RateLimiter(max_requests=50, window_seconds=60)   # 50 req/min
        self._limiters['yandex'] = RateLimiter(max_requests=20, window_seconds=60)   # 20 req/min
        self._limiters['telegram'] = RateLimiter(max_requests=5, window_seconds=60)  # 5 req/min (очень консервативно)
        self._limiters['twitter'] = RateLimiter(max_requests=15, window_seconds=900) # 15 req/15min
        self._limiters['default'] = RateLimiter(max_requests=30, window_seconds=60)  # Для остальных
    
    async def acquire(self, api_name: str, wait: bool = True) -> bool:
        """Получить разрешение для API"""
        limiter = self._limiters.get(api_name, self._limiters['default'])
        return await limiter.acquire(wait=wait)
    
    def get_all_stats(self) -> Dict:
        """Получить статистику всех лимитеров"""
        return {
            name: limiter.get_stats() 
            for name, limiter in self._limiters.items()
        }


# Глобальный rate limiter
_rate_limiters: Optional[APIRateLimiters] = None


def get_rate_limiters() -> APIRateLimiters:
    """Получить глобальный менеджер rate limiter'ов (singleton)"""
    global _rate_limiters
    
    if _rate_limiters is None:
        _rate_limiters = APIRateLimiters()
    
    return _rate_limiters