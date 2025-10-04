# Database Models

from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field


# News Model
class News(BaseModel):
    """News article model"""
    id: Optional[int] = None
    company_name: str
    title: str
    content: str
    url: str
    source: str  # 'google', 'yandex', 'bing', 'twitter', 'telegram', etc.
    publish_date: Optional[datetime] = None
    collected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    relevance_score: Optional[float] = None
    dedup_group: Optional[str] = None  # ID кластера дубликатов/перепечаток

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


# Company Model
class Company(BaseModel):
    """Company model for tracking searched companies"""
    id: Optional[int] = None
    name: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_searched: Optional[datetime] = None

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


# Source Model
class Source(BaseModel):
    """Source configuration model"""
    id: Optional[int] = None
    name: str
    type: str  # 'search_api' or 'social_media'
    enabled: bool = True
    last_used: Optional[datetime] = None

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
