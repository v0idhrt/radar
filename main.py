# Main FastAPI Application for Radar News Aggregator

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from pydantic import BaseModel
import asyncio
import os
from collections import defaultdict
from enum import Enum
import json

import httpx

from src.services.aggregator import NewsAggregator
from src.services.news_collector import NewsCollectorService
from src.core.database import Database
from src.core.config import config
from src.core.task_queue import get_task_queue, TaskPriority
from src.core.anomaly_filter import get_anomaly_filter
from src.services.logging_service import get_logger
from src.models.news import News

# Logging
logger = get_logger(__name__)

# FastAPI App
app = FastAPI(
    title="Radar News Aggregator",
    description="API для агрегации новостей из различных источников",
    version="1.0.0"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Database
Database.init_db()

# Global Instances
db = Database()
aggregator = NewsAggregator(db=db)
news_collector = NewsCollectorService(db=db)

# Task Queue
task_queue = get_task_queue(use_redis=False)  # Используем in-memory очередь

# Anomaly Filter
anomaly_filter = get_anomaly_filter()


# Настройки Ollama
OLLAMA_HOST = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'gemma2:9b')
OLLAMA_TIMEOUT = float(os.getenv('OLLAMA_TIMEOUT', '60'))


class ArticleAnalysisStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


# In-memory хранилище результатов анализа
analysis_state: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(dict)  # ticker -> article_id -> state
article_index: Dict[str, Dict[str, Any]] = {}  # article_id -> {"ticker": str, "state": {...}}
analysis_lock = asyncio.Lock()


# Task Handler для сбора новостей
async def handle_collect_news_task(payload: dict):
    """Обработчик задачи сбора новостей"""
    try:
        logger.info(f"Обработка задачи сбора новостей: {payload.get('company_name')}")
        
        await news_collector.collect_news_with_cache(
            company_name=payload['company_name'],
            max_results_per_source=payload.get('max_results_per_source', 30),
            use_search=payload.get('use_search', True),
            use_social=payload.get('use_social', False),
            save_to_db=payload.get('save_to_db', True),
            start_date=datetime.fromisoformat(payload['start_date']) if payload.get('start_date') else None,
            end_date=datetime.fromisoformat(payload['end_date']) if payload.get('end_date') else None,
        )
        
        logger.info(f"Задача сбора новостей завершена: {payload.get('company_name')}")
        
    except Exception as e:
        logger.error(f"Ошибка в задаче сбора новостей: {e}", exc_info=True)
        raise


# Регистрация обработчиков задач
task_queue.register_handler('collect_news', handle_collect_news_task)


async def handle_analyze_article_task(payload: dict):
    """Обработчик анализа одной новости"""
    ticker = payload.get("ticker", "").upper()
    article_data = payload.get("article")

    if not ticker or not article_data:
        logger.error("Некорректный payload для анализа новости: %s", payload)
        return

    article = AnalyzeNewsArticle(**article_data)
    await update_analysis_state(ticker, article, ArticleAnalysisStatus.PENDING)

    try:
        logger.info(f"Starting analysis for article {article.id} ({ticker})")
        result = await call_ollama_for_article(article)
        await update_analysis_state(ticker, article, ArticleAnalysisStatus.COMPLETED, result=result)
        logger.info(f"Analysis completed for article {article.id} ({ticker})")
    except Exception as exc:
        error_message = str(exc)
        logger.error(f"Ошибка анализа новости {article.id} ({ticker}): {error_message}", exc_info=True)
        await update_analysis_state(ticker, article, ArticleAnalysisStatus.FAILED, error=error_message)
        raise


task_queue.register_handler('analyze_news_article', handle_analyze_article_task)


@app.on_event("startup")
async def startup_event():
    """Запуск worker'ов при старте приложения"""
    logger.info("Запуск системы очередей задач")
    await task_queue.start_workers(num_workers=3)  # 3 worker'а для параллельной обработки
    logger.info("Система очередей задач запущена")


@app.on_event("shutdown")
async def shutdown_event():
    """Остановка worker'ов при завершении"""
    logger.info("Остановка системы очередей задач")
    await task_queue.stop_workers()
    logger.info("Система очередей задач остановлена")


# Response Models
class NewsArticle(BaseModel):
    """Frontend compatible format"""
    id: str
    headline: str
    content: str
    source: str
    timestamp: int
    url: str
    sentiment: Optional[str] = None


class AnalyzeNewsArticle(BaseModel):
    id: str
    headline: str
    content: str
    source: str
    timestamp: int
    url: str


class QueueNewsAnalysisRequest(BaseModel):
    ticker: str
    articles: List[AnalyzeNewsArticle]
    force: bool = False


class ArticleAnalysisResult(BaseModel):
    article_id: str
    status: ArticleAnalysisStatus
    sentiment: Optional[str] = None
    summary: Optional[str] = None
    error: Optional[str] = None
    updated_at: datetime


# Adapter Functions
def news_item_to_article(news: News) -> NewsArticle:
    """Convert NewsItem to frontend NewsArticle format"""
    article_id = str(news.id) if news.id else str(hash(news.url))
    sentiment = None

    entry = article_index.get(article_id)
    if entry:
        state = entry.get("state")
        if state and state.get("status") == ArticleAnalysisStatus.COMPLETED:
            sentiment = state.get("sentiment")

    return NewsArticle(
        id=article_id,
        headline=news.title,
        content=news.content or "",
        source=news.source,
        timestamp=int(news.publish_date.timestamp() * 1000) if news.publish_date else int(news.collected_at.timestamp() * 1000),
        url=news.url,
        sentiment=sentiment,
    )


async def call_ollama_for_article(article: AnalyzeNewsArticle) -> Dict[str, str]:
    """Вызов Ollama для анализа одной новости"""
    prompt = (
        "Ты опытный финансовый аналитик. Проанализируй следующую новость и оцени её тональность.\n"
        "Верни результат в формате JSON с ключами 'sentiment' (Positive, Negative или Neutral) и 'summary' (краткое описание на русском языке).\n"
        f"ID: {article.id}\n"
        f"Заголовок: {article.headline}\n"
        f"Текст: {article.content[:1200]}"
    )

    payload = {
        "model": OLLAMA_MODEL,
        "format": "json",
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "stream": False,
        "keep_alive": "5m",
    }

    async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT) as client:
        response = await client.post(
            f"{OLLAMA_HOST}/api/chat",
            json=payload
        )
        if response.status_code != 200:
            body = response.text[:500]
            raise RuntimeError(f"Ollama request failed with status {response.status_code}: {body}")

        data = response.json()
        content = data.get("message", {}).get("content")
        if not content:
            raise RuntimeError("Empty response content from Ollama")

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Failed to parse Ollama response: {exc}") from exc

        sentiment = parsed.get("sentiment")
        summary = parsed.get("summary")
        if not sentiment or not summary:
            raise RuntimeError("Ollama response missing required fields")

        normalized_sentiment = str(sentiment).strip().capitalize()
        if normalized_sentiment not in {"Positive", "Negative", "Neutral"}:
            normalized_sentiment = "Neutral"

        return {
            "sentiment": normalized_sentiment,
            "summary": str(summary).strip(),
        }


async def update_analysis_state(
    ticker: str,
    article: AnalyzeNewsArticle,
    status: ArticleAnalysisStatus,
    result: Optional[Dict[str, str]] = None,
    error: Optional[str] = None,
):
    ticker_key = ticker.upper()
    async with analysis_lock:
        state = analysis_state[ticker_key].get(article.id)
        if not state:
            state = {
                "article": article.model_dump(),
                "status": status,
                "sentiment": None,
                "summary": None,
                "error": None,
                "updated_at": datetime.now(timezone.utc),
            }
            analysis_state[ticker_key][article.id] = state
            article_index[article.id] = {"ticker": ticker_key, "state": state}

        state["status"] = status
        state["updated_at"] = datetime.now(timezone.utc)
        state["article"] = article.model_dump()
        if result:
            state["sentiment"] = result.get("sentiment")
            state["summary"] = result.get("summary")
            state["error"] = None
        if error:
            state["error"] = error


def state_to_result(article_id: str, state: Dict[str, Any]) -> ArticleAnalysisResult:
    status_value = state.get("status", ArticleAnalysisStatus.PENDING)
    if isinstance(status_value, ArticleAnalysisStatus):
        status = status_value
    else:
        status = ArticleAnalysisStatus(str(status_value))

    updated_at_value = state.get("updated_at")
    if isinstance(updated_at_value, datetime):
        updated_at = updated_at_value
    else:
        updated_at = datetime.now(timezone.utc)

    return ArticleAnalysisResult(
        article_id=article_id,
        status=status,
        sentiment=state.get("sentiment"),
        summary=state.get("summary"),
        error=state.get("error"),
        updated_at=updated_at,
    )


async def get_ticker_results_snapshot(ticker: str) -> List[ArticleAnalysisResult]:
    ticker_key = ticker.upper()
    async with analysis_lock:
        items = list(analysis_state.get(ticker_key, {}).items())
    return [state_to_result(article_id, state) for article_id, state in items]


# Request Models
class CollectNewsRequest(BaseModel):
    company_name: str
    max_results_per_source: int = 30
    use_search: bool = True
    use_social: bool = False
    save_to_db: bool = True
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class AnomalyWebhook(BaseModel):
    """Webhook payload from Finam-Service"""
    ticker: str
    z_score: float
    delta: float
    direction: str  # "buy" or "sell"
    price: float
    timestamp: str
    timeframe: str  # "M1", "M5", "M30"


# Response Models (continued)
class NewsItem(BaseModel):
    company_name: str
    title: str
    content: str
    url: str
    source: str
    publish_date: datetime
    collected_at: datetime
    relevance_score: Optional[float] = None


class AggregateResponse(BaseModel):
    company_name: str
    total_results: int
    news: List[NewsItem]
    sources_used: dict


class StatsResponse(BaseModel):
    total_articles: int
    by_source: dict
    available_sources: dict


# Endpoints
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Radar News Aggregator API",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "collect": "/api/collect",
            "news": "/api/news",
            "stats": "/api/stats",
            "sources": "/api/sources"
        }
    }


@app.post("/api/collect", response_model=AggregateResponse)
async def collect_news(request: CollectNewsRequest):
    """
    Собрать новости о компании из всех источников
    """
    logger.info(f"API запрос на сбор новостей для '{request.company_name}'")

    try:
        # Parse dates if provided
        start_date = datetime.fromisoformat(request.start_date.replace('Z', '+00:00')) if request.start_date else None
        end_date = datetime.fromisoformat(request.end_date.replace('Z', '+00:00')) if request.end_date else None

        news_items = await aggregator.collect_news(
            company_name=request.company_name,
            max_results_per_source=request.max_results_per_source,
            use_search=request.use_search,
            use_social=request.use_social,
            save_to_db=request.save_to_db,
            start_date=start_date,
            end_date=end_date
        )

        # Подсчет источников
        sources_count = {}
        for item in news_items:
            sources_count[item.source] = sources_count.get(item.source, 0) + 1

        return AggregateResponse(
            company_name=request.company_name,
            total_results=len(news_items),
            news=[NewsItem(**item.dict()) for item in news_items],
            sources_used=sources_count
        )

    except Exception as e:
        logger.error(f"Ошибка сбора новостей: {e}", exc_info=e)
        raise HTTPException(status_code=500, detail=f"Ошибка сбора новостей: {str(e)}")


@app.get("/api/news/{company_name}", response_model=List[NewsItem])
async def get_news(
    company_name: str,
    start_date: Optional[str] = Query(None, description="Дата начала в ISO формате"),
    end_date: Optional[str] = Query(None, description="Дата окончания в ISO формате"),
    limit: int = Query(100, ge=1, le=500, description="Лимит результатов")
):
    """
    Получить новости из базы данных
    """
    logger.info(f"API запрос на получение новостей для '{company_name}'")

    try:
        # Parse dates if provided
        start = datetime.fromisoformat(start_date.replace('Z', '+00:00')) if start_date else None
        end = datetime.fromisoformat(end_date.replace('Z', '+00:00')) if end_date else None

        # Get news with optional date filtering
        if start or end:
            news_items = db.get_news_by_company_and_period(company_name, start, end, limit)
        else:
            news_items = aggregator.get_news_from_db(company_name, limit)

        return [NewsItem(**item.dict()) for item in news_items]

    except Exception as e:
        logger.error(f"Ошибка получения новостей: {e}", exc_info=e)
        raise HTTPException(status_code=500, detail=f"Ошибка получения новостей: {str(e)}")


@app.get("/api/stats/{company_name}", response_model=StatsResponse)
async def get_stats(company_name: str):
    """
    Получить статистику по новостям компании
    """
    logger.info(f"API запрос на статистику для '{company_name}'")

    try:
        stats = aggregator.get_stats(company_name)
        return StatsResponse(**stats)

    except Exception as e:
        logger.error(f"Ошибка получения статистики: {e}", exc_info=e)
        raise HTTPException(status_code=500, detail=f"Ошибка получения статистики: {str(e)}")


@app.get("/api/sources")
async def get_available_sources():
    """
    Получить список доступных источников
    """
    logger.info("API запрос на список источников")

    try:
        sources = aggregator.get_available_sources()
        return {
            "search_engines": sources['search'],
            "social_media": sources['social'],
            "total_available": sum(1 for v in {**sources['search'], **sources['social']}.values() if v)
        }

    except Exception as e:
        logger.error(f"Ошибка получения источников: {e}", exc_info=e)
        raise HTTPException(status_code=500, detail=f"Ошибка получения источников: {str(e)}")


@app.get("/health")
async def health_check():
    """
    Проверка здоровья сервиса
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "database": "connected" if db else "disconnected"
    }


@app.get("/api/ticker/{ticker}/company")
async def get_company_by_ticker(ticker: str):
    """
    Получить название компании по тикеру
    """
    logger.info(f"API запрос на получение компании для тикера '{ticker}'")

    try:
        company_name = db.get_company_by_ticker(ticker.upper())
        if not company_name:
            raise HTTPException(status_code=404, detail=f"Тикер '{ticker}' не найден")

        return {
            "ticker": ticker.upper(),
            "company_name": company_name
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения компании: {e}", exc_info=e)
        raise HTTPException(status_code=500, detail=f"Ошибка получения компании: {str(e)}")


@app.get("/api/tickers")
async def get_all_tickers():
    """
    Получить список всех тикеров
    """
    logger.info("API запрос на получение всех тикеров")

    try:
        tickers = db.get_all_tickers()
        return {
            "total": len(tickers),
            "tickers": tickers
        }

    except Exception as e:
        logger.error(f"Ошибка получения тикеров: {e}", exc_info=e)
        raise HTTPException(status_code=500, detail=f"Ошибка получения тикеров: {str(e)}")


@app.get("/api/news/ticker/{ticker}", response_model=List[NewsArticle])
async def get_news_by_ticker(
    ticker: str,
    start_date: Optional[str] = Query(None, description="Дата начала в ISO формате"),
    end_date: Optional[str] = Query(None, description="Дата окончания в ISO формате"),
    limit: int = Query(100, ge=1, le=500, description="Лимит результатов")
):
    """
    Получить новости по тикеру (frontend compatible format)
    """
    logger.info(f"API запрос на получение новостей для тикера '{ticker}'")

    try:
        # Get company name by ticker
        company_name = db.get_company_by_ticker(ticker.upper())
        if not company_name:
            raise HTTPException(status_code=404, detail=f"Тикер '{ticker}' не найден")

        # Parse dates if provided
        start = datetime.fromisoformat(start_date.replace('Z', '+00:00')) if start_date else None
        end = datetime.fromisoformat(end_date.replace('Z', '+00:00')) if end_date else None

        # Get news with optional date filtering
        if start or end:
            news_items = db.get_news_by_company_and_period(company_name, start, end, limit)
        else:
            news_items = aggregator.get_news_from_db(company_name, limit)

        # Convert to frontend format
        articles = [news_item_to_article(news) for news in news_items]
        return articles

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения новостей по тикеру: {e}", exc_info=e)
        raise HTTPException(status_code=500, detail=f"Ошибка получения новостей: {str(e)}")


@app.post("/api/analyze/news")
async def queue_news_analysis(request: QueueNewsAnalysisRequest):
    ticker_key = request.ticker.upper()
    queued = 0
    skipped_completed = 0
    skipped_pending = 0

    for article in request.articles:
        article_data = article.model_dump()
        should_queue = False

        async with analysis_lock:
            state = analysis_state[ticker_key].get(article.id)
            if not state:
                state = {
                    "article": article_data,
                    "status": ArticleAnalysisStatus.PENDING,
                    "sentiment": None,
                    "summary": None,
                    "error": None,
                    "updated_at": datetime.now(timezone.utc),
                }
                analysis_state[ticker_key][article.id] = state
                article_index[article.id] = {"ticker": ticker_key, "state": state}
                should_queue = True
            else:
                state["article"] = article_data
                current_status = state.get("status", ArticleAnalysisStatus.PENDING)
                if not isinstance(current_status, ArticleAnalysisStatus):
                    current_status = ArticleAnalysisStatus(str(current_status))

                if request.force:
                    should_queue = True
                elif current_status == ArticleAnalysisStatus.COMPLETED:
                    skipped_completed += 1
                    should_queue = False
                elif current_status == ArticleAnalysisStatus.PENDING:
                    skipped_pending += 1
                    should_queue = False
                else:
                    should_queue = True

                if should_queue:
                    state["sentiment"] = None
                    state["summary"] = None
                    state["error"] = None
                    state["status"] = ArticleAnalysisStatus.PENDING
                    state["updated_at"] = datetime.now(timezone.utc)

        if should_queue:
            await task_queue.add_task(
                'analyze_news_article',
                payload={'ticker': ticker_key, 'article': article_data},
                priority=TaskPriority.HIGH,
                deduplicate=False
            )
            queued += 1

    results = await get_ticker_results_snapshot(ticker_key)
    pending_count = sum(1 for item in results if item.status == ArticleAnalysisStatus.PENDING)

    return {
        "ticker": ticker_key,
        "queued": queued,
        "skipped": {
            "completed": skipped_completed,
            "pending": skipped_pending,
        },
        "pending": pending_count,
        "results": [item.model_dump(mode="json") for item in results],
    }


@app.get("/api/analyze/news/{ticker}", response_model=List[ArticleAnalysisResult])
async def get_news_analysis_status(
    ticker: str,
    article_ids: Optional[List[str]] = Query(None, description="Список конкретных ID новостей")
):
    ticker_key = ticker.upper()
    results = await get_ticker_results_snapshot(ticker_key)

    if article_ids:
        filter_ids = set(article_ids)
        results = [item for item in results if item.article_id in filter_ids]

    return results


@app.post("/api/webhook/anomaly")
async def handle_anomaly_webhook(anomaly: AnomalyWebhook):
    """
    Webhook от Finam-Service при обнаружении аномалии z-score
    ОПТИМИЗИРОВАНО: Умная фильтрация + асинхронная очередь задач
    """
    logger.info(f"🔔 Anomaly received: {anomaly.ticker} | Z-Score: {anomaly.z_score:.2f} | {anomaly.direction.upper()}")

    try:
        # Получить название компании по тикеру (убрать @MISX)
        ticker_clean = anomaly.ticker.replace('@MISX', '')
        company_name = db.get_company_by_ticker(ticker_clean)

        if not company_name:
            logger.warning(f"Ticker {anomaly.ticker} not found in database")
            return {"status": "skipped", "reason": "ticker_not_found", "ticker": anomaly.ticker}

        # УМНАЯ ФИЛЬТРАЦИЯ: Оценка значимости аномалии
        anomaly_score = anomaly_filter.evaluate_anomaly(
            ticker=anomaly.ticker,
            z_score=anomaly.z_score,
            delta=anomaly.delta,
            price=anomaly.price,
            timestamp=anomaly.timestamp,
            timeframe=anomaly.timeframe
        )

        # Пропускаем незначительные аномалии
        if not anomaly_score.is_significant:
            logger.info(
                f"⏭️  Anomaly skipped (low score): {anomaly.ticker} | "
                f"score={anomaly_score.score:.1f} | reasons={anomaly_score.reasons}"
            )
            return {
                "status": "filtered",
                "reason": "low_significance_score",
                "ticker": anomaly.ticker,
                "score": anomaly_score.score,
                "threshold": 50,
                "details": anomaly_score.to_dict()
            }

        # Сохранить значимую аномалию в БД
        anomaly_id = db.add_anomaly(
            ticker=anomaly.ticker,
            company_name=company_name,
            z_score=anomaly.z_score,
            delta=anomaly.delta,
            direction=anomaly.direction,
            price=anomaly.price,
            timestamp=anomaly.timestamp,
            timeframe=anomaly.timeframe,
            news_count=0  # Будет обновлено после сбора
        )

        # Приоритет основан на оценке значимости
        if anomaly_score.score >= 80:
            priority = TaskPriority.HIGH
        elif anomaly_score.score >= 60:
            priority = TaskPriority.NORMAL
        else:
            priority = TaskPriority.LOW
        
        # Добавить задачу сбора новостей в ОЧЕРЕДЬ
        task_id = await task_queue.add_task(
            task_type='collect_news',
            payload={
                'company_name': company_name,
                'max_results_per_source': 30,
                'use_search': True,
                'use_social': False,  # Отключено (Telegram flood wait)
                'save_to_db': True,
                'anomaly_id': anomaly_id,
            },
            priority=priority,
            deduplicate=True,
            dedup_window=300  # 5 минут
        )

        logger.info(
            f"✅ Significant anomaly queued: ID={anomaly_id}, task={task_id}, "
            f"priority={priority.name}, score={anomaly_score.score:.1f}"
        )

        return {
            "status": "queued",
            "anomaly_id": anomaly_id,
            "task_id": task_id,
            "ticker": anomaly.ticker,
            "company_name": company_name,
            "z_score": anomaly.z_score,
            "priority": priority.name,
            "direction": anomaly.direction,
            "significance_score": anomaly_score.score,
            "reasons": anomaly_score.reasons,
            "message": "Significant anomaly queued for processing"
        }

    except Exception as e:
        logger.error(f"Error processing anomaly: {e}", exc_info=e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/quotes/{ticker}")
async def get_ticker_quotes(ticker: str):
    """
    Получить котировки от Finam-Service
    """
    logger.info(f"Fetching quotes for {ticker} from Finam-Service")

    try:
        import requests
        from datetime import timedelta

        # Добавить @MISX если отсутствует (Finam требует этот формат)
        ticker_finam = ticker.upper()
        if not ticker_finam.endswith('@MISX'):
            ticker_finam = f"{ticker_finam}@MISX"

        # Формируем запрос к Finam
        end_ts = int(datetime.now(timezone.utc).timestamp())

        response = requests.get(
            "http://localhost:8001/bars",
            params={"ticker_name": ticker_finam, "timestamp": end_ts - 60*60*2},  # 2 часа назад
            timeout=10
        )

        if response.ok:
            data = response.json()
            bars = data.get("bars", [])

            # Конвертировать в StockPoint формат для frontend
            points = []
            base_time = datetime.now(timezone.utc) - timedelta(hours=2)

            for i, bar in enumerate(bars):
                point_time = base_time + timedelta(minutes=i)
                points.append({
                    "date": point_time.isoformat().split('T')[0],
                    "price": bar["close"]
                })

            return {"ticker": ticker, "quotes": points}
        else:
            raise HTTPException(status_code=502, detail="Finam service unavailable")

    except requests.exceptions.RequestException as e:
        logger.error(f"Error connecting to Finam: {e}")
        raise HTTPException(status_code=502, detail=f"Finam service error: {str(e)}")
    except Exception as e:
        logger.error(f"Error fetching quotes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/anomalies/impactful")
async def get_impactful_anomalies(limit: int = Query(10, ge=1, le=50)):
    """
    Получить топ аномалий с новостями (важные события для главной страницы)
    """
    logger.info(f"Fetching top {limit} impactful anomalies")

    try:
        anomalies = db.get_impactful_anomalies(limit)

        # Для каждой аномалии добавить топ новость
        result = []
        for anomaly in anomalies:
            # Получить одну топ-новость для этой компании
            news_items = db.get_news_by_company(anomaly['company_name'], limit=1)

            top_news = None
            if news_items:
                news = news_items[0]
                top_news = {
                    "headline": news.title,
                    "url": news.url,
                    "source": news.source
                }

            result.append({
                "id": anomaly['id'],
                "ticker": anomaly['ticker'],
                "company_name": anomaly['company_name'],
                "z_score": anomaly['z_score'],
                "delta": anomaly['delta'],
                "direction": anomaly['direction'],
                "price": anomaly['price'],
                "timestamp": anomaly['timestamp'],
                "timeframe": anomaly['timeframe'],
                "news_count": anomaly['news_count'],
                "top_news": top_news
            })

        return {"anomalies": result, "total": len(result)}

    except Exception as e:
        logger.error(f"Error fetching impactful anomalies: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/queue/stats")
async def get_queue_stats():
    """
    Получить статистику очереди задач
    """
    try:
        queue_stats = task_queue.get_stats()
        cache_stats = news_collector.get_cache_stats()
        
        return {
            "queue": queue_stats,
            "cache": cache_stats,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    except Exception as e:
        logger.error(f"Error fetching queue stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/system/stats")
async def get_system_stats():
    """
    Получить полную статистику системы (очередь, кэш, rate limits)
    """
    try:
        from src.core.rate_limiter import get_rate_limiters
        
        rate_limiters = get_rate_limiters()
        
        return {
            "queue": task_queue.get_stats(),
            "cache": news_collector.get_cache_stats(),
            "rate_limits": rate_limiters.get_all_stats(),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Error fetching system stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/news/hot", response_model=List[NewsArticle])
async def get_hot_news(
    hours: int = Query(24, ge=1, le=168, description="Количество часов для поиска горячих новостей"),
    limit: int = Query(50, ge=1, le=200, description="Максимальное количество новостей")
):
    """
    Получить "горячие новости" - свежие новости, связанные со значимыми аномалиями рынка
    
    Горячие новости - это новости, опубликованные за последние N часов и связанные
    с компаниями, в которых были обнаружены значимые аномалии цен (высокий z-score).
    Новости отсортированы по важности аномалии и времени публикации.
    """
    logger.info(f"API запрос на получение горячих новостей (hours={hours}, limit={limit})")
    
    try:
        # Получить горячие новости из БД
        hot_news = db.get_hot_news(hours=hours, limit=limit)
        
        # Конвертировать в формат для frontend
        articles = [news_item_to_article(news) for news in hot_news]
        
        logger.info(f"Найдено {len(articles)} горячих новостей за последние {hours} часов")
        
        return articles
        
    except Exception as e:
        logger.error(f"Ошибка получения горячих новостей: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ошибка получения горячих новостей: {str(e)}")


@app.get("/api/anomaly/ticker/{ticker}/stats")
async def get_ticker_anomaly_stats(ticker: str):
    """
    Получить статистику аномалий для тикера
    """
    try:
        stats = anomaly_filter.get_ticker_stats(ticker.upper())
        return stats
    except Exception as e:
        logger.error(f"Error fetching ticker stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class ForecastRequest(BaseModel):
    ticker: str
    stock_data: List[Dict[str, Any]]  # [{date, price}, ...]
    analyzed_news: List[Dict[str, Any]]  # Analyzed news with sentiment


class ForecastResponse(BaseModel):
    forecast: List[Dict[str, Any]]  # [{date, price}, ...]
    analysis: str


async def call_ollama_for_forecast(
    ticker: str,
    stock_data: List[Dict[str, Any]],
    analyzed_news: List[Dict[str, Any]]
) -> ForecastResponse:
    """Вызов Ollama для генерации прогноза цен"""

    # Подготовка данных для промпта
    recent_prices = stock_data[-10:] if len(stock_data) > 10 else stock_data
    price_summary = ", ".join([f"{p['date']}: ${p['price']:.2f}" for p in recent_prices])

    # Анализ новостей
    news_summary = []
    sentiment_counts = {"Positive": 0, "Negative": 0, "Neutral": 0}

    for news in analyzed_news[-5:]:  # Последние 5 новостей
        sentiment = news.get("sentiment", "Neutral")
        sentiment_counts[sentiment] = sentiment_counts.get(sentiment, 0) + 1
        news_summary.append(f"- {news.get('headline', '')[:100]} (Sentiment: {sentiment})")

    news_text = "\n".join(news_summary) if news_summary else "Нет проанализированных новостей"

    prompt = (
        f"Ты опытный финансовый аналитик. Проанализируй данные по акциям {ticker} и создай 7-дневный прогноз цен.\n\n"
        f"Последние цены:\n{price_summary}\n\n"
        f"Недавние новости:\n{news_text}\n\n"
        f"Статистика тональности новостей: Positive={sentiment_counts['Positive']}, "
        f"Negative={sentiment_counts['Negative']}, Neutral={sentiment_counts['Neutral']}\n\n"
        "Верни результат в формате JSON:\n"
        "{\n"
        '  "forecast": [{"date": "YYYY-MM-DD", "price": число}, ...],  // 7 дней\n'
        '  "analysis": "подробное обоснование прогноза на русском языке (2-3 предложения)"\n'
        "}\n"
    )

    payload = {
        "model": OLLAMA_MODEL,
        "format": "json",
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "stream": False,
        "keep_alive": "5m",
    }

    async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT) as client:
        response = await client.post(
            f"{OLLAMA_HOST}/api/chat",
            json=payload
        )
        if response.status_code != 200:
            body = response.text[:500]
            raise RuntimeError(f"Ollama forecast request failed with status {response.status_code}: {body}")

        data = response.json()
        content = data.get("message", {}).get("content")
        if not content:
            raise RuntimeError("Empty response content from Ollama")

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Failed to parse Ollama forecast response: {exc}") from exc

        forecast = parsed.get("forecast")
        analysis = parsed.get("analysis")

        if not forecast or not analysis:
            raise RuntimeError("Ollama forecast response missing required fields")

        return ForecastResponse(
            forecast=forecast,
            analysis=str(analysis).strip()
        )


@app.post("/api/forecast/{ticker}", response_model=ForecastResponse)
async def generate_price_forecast(ticker: str, request: ForecastRequest):
    """
    Генерация прогноза цен на акции с использованием AI
    """
    logger.info(f"API запрос на генерацию прогноза для '{ticker}'")

    try:
        # Валидация
        if not request.stock_data or len(request.stock_data) < 5:
            raise HTTPException(
                status_code=400,
                detail="Недостаточно исторических данных для прогноза (минимум 5 точек)"
            )

        # Генерация прогноза через Ollama
        forecast_result = await call_ollama_for_forecast(
            ticker=ticker,
            stock_data=request.stock_data,
            analyzed_news=request.analyzed_news or []
        )

        logger.info(f"Прогноз для '{ticker}' успешно сгенерирован: {len(forecast_result.forecast)} точек")

        return forecast_result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка генерации прогноза для {ticker}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ошибка генерации прогноза: {str(e)}")


# Main Entry Point
if __name__ == "__main__":
    import uvicorn

    logger.info("Запуск Radar News Aggregator API...")

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info"
    )
