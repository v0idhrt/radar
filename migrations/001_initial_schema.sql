-- Migration 001: Initial Schema
-- Created: 2025-10-03
-- Description: Create initial database schema with companies, sources, and news tables

-- Companies Table
CREATE TABLE IF NOT EXISTS companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    last_searched TEXT
);

-- Sources Table
CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    type TEXT NOT NULL CHECK(type IN ('search_api', 'social_media')),
    enabled INTEGER DEFAULT 1 CHECK(enabled IN (0, 1)),
    last_used TEXT
);

-- News Table
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
    UNIQUE(url, company_name)
);

-- Indexes for Performance
CREATE INDEX IF NOT EXISTS idx_news_company ON news(company_name);
CREATE INDEX IF NOT EXISTS idx_news_source ON news(source);
CREATE INDEX IF NOT EXISTS idx_news_publish_date ON news(publish_date);
CREATE INDEX IF NOT EXISTS idx_news_url ON news(url);
CREATE INDEX IF NOT EXISTS idx_companies_name ON companies(name);
CREATE INDEX IF NOT EXISTS idx_sources_name ON sources(name);

-- Insert default sources
INSERT OR IGNORE INTO sources (name, type, enabled) VALUES
    ('google', 'search_api', 1),
    ('yandex', 'search_api', 1),
    ('bing', 'search_api', 1),
    ('serper', 'search_api', 1),
    ('twitter', 'social_media', 1),
    ('telegram', 'social_media', 1);
