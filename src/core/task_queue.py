"""
Система очередей для асинхронной обработки задач
Поддерживает Redis (если доступен) или in-memory queue
"""

import asyncio
import json
from typing import Optional, Dict, Any, Callable, Awaitable
from datetime import datetime, timezone
from enum import Enum
import hashlib

from src.services.logging_service import get_logger

logger = get_logger(__name__)


class TaskPriority(Enum):
    HIGH = 1
    NORMAL = 2
    LOW = 3


class TaskStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Task:
    """Задача для обработки"""
    
    def __init__(
        self,
        task_id: str,
        task_type: str,
        payload: Dict[str, Any],
        priority: TaskPriority = TaskPriority.NORMAL
    ):
        self.task_id = task_id
        self.task_type = task_type
        self.payload = payload
        self.priority = priority
        self.created_at = datetime.now(timezone.utc)
        self.status = TaskStatus.PENDING
    
    def __lt__(self, other):
        """Сравнение для PriorityQueue (по приоритету, затем по времени)"""
        if self.priority.value != other.priority.value:
            return self.priority.value < other.priority.value
        return self.created_at < other.created_at
    
    def __eq__(self, other):
        """Равенство задач"""
        return self.task_id == other.task_id
        
    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "payload": self.payload,
            "priority": self.priority.value,
            "created_at": self.created_at.isoformat(),
            "status": self.status.value
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Task':
        task = cls(
            task_id=data["task_id"],
            task_type=data["task_type"],
            payload=data["payload"],
            priority=TaskPriority(data.get("priority", TaskPriority.NORMAL.value))
        )
        task.created_at = datetime.fromisoformat(data["created_at"])
        task.status = TaskStatus(data.get("status", TaskStatus.PENDING.value))
        return task


class TaskQueue:
    """Асинхронная очередь задач с дедупликацией"""
    
    def __init__(self, use_redis: bool = False, redis_url: str = "redis://localhost:6379"):
        self.use_redis = use_redis
        self.redis_url = redis_url
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._processing: Dict[str, Task] = {}
        self._handlers: Dict[str, Callable[[Dict[str, Any]], Awaitable[Any]]] = {}
        self._workers: list = []
        self._running = False
        self._task_cache: Dict[str, float] = {}  # Для дедупликации: task_hash -> timestamp
        self._redis_client = None
        
        if use_redis:
            self._init_redis()
    
    def _init_redis(self):
        """Инициализация Redis (опционально)"""
        try:
            import redis.asyncio as redis
            self._redis_client = redis.from_url(self.redis_url, decode_responses=True)
            logger.info("Redis подключен для очереди задач")
        except ImportError:
            logger.warning("Redis не доступен, используется in-memory queue")
            self.use_redis = False
        except Exception as e:
            logger.error(f"Ошибка подключения к Redis: {e}")
            self.use_redis = False
    
    def register_handler(self, task_type: str, handler: Callable[[Dict[str, Any]], Awaitable[Any]]):
        """Регистрация обработчика для типа задачи"""
        self._handlers[task_type] = handler
        logger.info(f"Зарегистрирован обработчик для '{task_type}'")
    
    def _get_task_hash(self, task_type: str, payload: Dict[str, Any]) -> str:
        """Генерация хэша для дедупликации задач"""
        # Создаем детерминированный хэш на основе типа и ключевых параметров
        key_data = f"{task_type}:{json.dumps(payload, sort_keys=True)}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    async def add_task(
        self,
        task_type: str,
        payload: Dict[str, Any],
        priority: TaskPriority = TaskPriority.NORMAL,
        deduplicate: bool = True,
        dedup_window: int = 300  # 5 минут
    ) -> Optional[str]:
        """Добавление задачи в очередь с дедупликацией"""
        
        # Проверка дедупликации
        if deduplicate:
            task_hash = self._get_task_hash(task_type, payload)
            current_time = datetime.now(timezone.utc).timestamp()
            
            if task_hash in self._task_cache:
                last_time = self._task_cache[task_hash]
                if current_time - last_time < dedup_window:
                    logger.debug(f"Задача {task_type} пропущена (дубликат в течение {dedup_window}s)")
                    return None
            
            self._task_cache[task_hash] = current_time
        
        # Создание задачи
        task_id = f"{task_type}_{datetime.now(timezone.utc).timestamp()}"
        task = Task(task_id, task_type, payload, priority)
        
        if self.use_redis and self._redis_client:
            # Сохранение в Redis
            await self._redis_client.lpush(
                f"task_queue:{priority.value}",
                json.dumps(task.to_dict())
            )
        else:
            # Добавление в in-memory очередь
            await self._queue.put((priority.value, task))
        
        logger.info(f"Задача добавлена: {task_id} [{task_type}] приоритет={priority.name}")
        return task_id
    
    async def _worker(self, worker_id: int):
        """Worker для обработки задач из очереди"""
        logger.info(f"Worker {worker_id} запущен")
        
        while self._running:
            try:
                task = None
                
                if self.use_redis and self._redis_client:
                    # Получение из Redis (блокирующее чтение)
                    for priority in TaskPriority:
                        result = await self._redis_client.brpop(
                            f"task_queue:{priority.value}",
                            timeout=1
                        )
                        if result:
                            _, task_data = result
                            task = Task.from_dict(json.loads(task_data))
                            break
                else:
                    # Получение из in-memory очереди
                    try:
                        priority, task = await asyncio.wait_for(
                            self._queue.get(),
                            timeout=1.0
                        )
                    except asyncio.TimeoutError:
                        continue
                
                if not task:
                    continue
                
                # Обработка задачи
                task.status = TaskStatus.PROCESSING
                self._processing[task.task_id] = task
                
                handler = self._handlers.get(task.task_type)
                if not handler:
                    logger.error(f"Обработчик не найден для {task.task_type}")
                    task.status = TaskStatus.FAILED
                    continue
                
                try:
                    logger.info(f"Worker {worker_id} обрабатывает {task.task_id}")
                    await handler(task.payload)
                    task.status = TaskStatus.COMPLETED
                    logger.info(f"Worker {worker_id} завершил {task.task_id}")
                except Exception as e:
                    logger.error(f"Worker {worker_id} ошибка в {task.task_id}: {e}", exc_info=True)
                    task.status = TaskStatus.FAILED
                finally:
                    self._processing.pop(task.task_id, None)
                    
            except Exception as e:
                logger.error(f"Worker {worker_id} критическая ошибка: {e}", exc_info=True)
                await asyncio.sleep(1)
        
        logger.info(f"Worker {worker_id} остановлен")
    
    async def start_workers(self, num_workers: int = 3):
        """Запуск worker'ов для обработки задач"""
        if self._running:
            logger.warning("Workers уже запущены")
            return
        
        self._running = True
        logger.info(f"Запуск {num_workers} workers")
        
        for i in range(num_workers):
            worker = asyncio.create_task(self._worker(i))
            self._workers.append(worker)
    
    async def stop_workers(self):
        """Остановка всех worker'ов"""
        logger.info("Остановка workers")
        self._running = False
        
        for worker in self._workers:
            worker.cancel()
        
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        
        if self._redis_client:
            await self._redis_client.close()
        
        logger.info("Workers остановлены")
    
    def get_stats(self) -> Dict[str, Any]:
        """Получение статистики очереди"""
        return {
            "queue_size": self._queue.qsize() if not self.use_redis else "N/A",
            "processing": len(self._processing),
            "workers": len(self._workers),
            "running": self._running,
            "backend": "redis" if self.use_redis else "memory"
        }


# Глобальная очередь задач
_task_queue: Optional[TaskQueue] = None


def get_task_queue(use_redis: bool = False) -> TaskQueue:
    """Получение глобальной очереди задач (singleton)"""
    global _task_queue
    
    if _task_queue is None:
        _task_queue = TaskQueue(use_redis=use_redis)
    
    return _task_queue
