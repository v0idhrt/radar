# Main FastAPI Application for Radar News Aggregator

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List
from datetime import datetime, timezone
from pydantic import BaseModel

from src.services.aggregator import NewsAggregator
from src.core.database import Database
from src.core.config import config
from src.services.logging_service import get_logger

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


# Request Models
class CollectNewsRequest(BaseModel):
    company_name: str
    max_results_per_source: int = 30
    use_search: bool = True
    use_social: bool = False
    save_to_db: bool = True
    start_date: Optional[str] = None
    end_date: Optional[str] = None


# Response Models
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
