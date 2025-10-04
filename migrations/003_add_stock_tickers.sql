-- Migration 003: Add stock_tickers table for ticker to company name mapping

CREATE TABLE IF NOT EXISTS stock_tickers (
    ticker TEXT PRIMARY KEY,
    company_name TEXT NOT NULL,
    exchange TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT
);

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_tickers_company ON stock_tickers(company_name);
CREATE INDEX IF NOT EXISTS idx_tickers_exchange ON stock_tickers(exchange);

-- Insert Moscow Exchange tickers
INSERT OR IGNORE INTO stock_tickers (ticker, company_name, exchange, created_at) VALUES
('SBER', 'Сбербанк', 'MISX', datetime('now')),
('GAZP', 'Газпром', 'MISX', datetime('now')),
('LKOH', 'Лукойл', 'MISX', datetime('now')),
('GMKN', 'Норильский никель', 'MISX', datetime('now')),
('YNDX', 'Яндекс', 'MISX', datetime('now')),
('ROSN', 'Роснефть', 'MISX', datetime('now')),
('NVTK', 'Новатэк', 'MISX', datetime('now')),
('TATN', 'Татнефть', 'MISX', datetime('now')),
('SNGS', 'Сургутнефтегаз', 'MISX', datetime('now')),
('MTSS', 'МТС', 'MISX', datetime('now')),
('MGNT', 'Магнит', 'MISX', datetime('now')),
('ALRS', 'Алроса', 'MISX', datetime('now')),
('CHMF', 'Северсталь', 'MISX', datetime('now')),
('NLMK', 'НЛМК', 'MISX', datetime('now')),
('PLZL', 'Полюс', 'MISX', datetime('now')),
('VTBR', 'ВТБ', 'MISX', datetime('now')),
('AFLT', 'Аэрофлот', 'MISX', datetime('now')),
('IRAO', 'Интер РАО', 'MISX', datetime('now')),
('HYDR', 'РусГидро', 'MISX', datetime('now')),
('MOEX', 'Московская биржа', 'MISX', datetime('now')),
('RUAL', 'Русал', 'MISX', datetime('now')),
('MAGN', 'ММК', 'MISX', datetime('now')),
('AFKS', 'АФК Система', 'MISX', datetime('now')),
('PIKK', 'ПИК', 'MISX', datetime('now')),
('TRNFP', 'Транснефть (ап)', 'MISX', datetime('now')),
('SIBN', 'Газпром нефть', 'MISX', datetime('now')),
('POLY', 'Polymetal', 'MISX', datetime('now')),
('RTKM', 'Ростелеком', 'MISX', datetime('now')),
('PHOR', 'ФосАгро', 'MISX', datetime('now')),
('FEES', 'ФСК ЕЭС', 'MISX', datetime('now')),
('OZON', 'Ozon', 'MISX', datetime('now')),
('RNFT', 'РуссНефть', 'MISX', datetime('now')),
('TCSG', 'TCS Group', 'MISX', datetime('now')),
('UPRO', 'Юнипро', 'MISX', datetime('now')),
('BSPB', 'Банк Санкт-Петербург', 'MISX', datetime('now')),
('CBOM', 'МКБ', 'MISX', datetime('now')),
('AKRN', 'Акрон', 'MISX', datetime('now')),
('FLOT', 'Совкомфлот', 'MISX', datetime('now')),
('RENI', 'Ренессанс страхование', 'MISX', datetime('now')),
('VKCO', 'VK', 'MISX', datetime('now')),
('FIXP', 'Fix Price', 'MISX', datetime('now')),
('ENPG', 'ЭН+ Group', 'MISX', datetime('now')),
('OGKB', 'ОГК-2', 'MISX', datetime('now')),
('TGKA', 'ТГК-1', 'MISX', datetime('now')),
('MVID', 'М.Видео', 'MISX', datetime('now')),
('LSRG', 'ЛСР', 'MISX', datetime('now')),
('SMLT', 'Самолет', 'MISX', datetime('now')),
('FIVE', 'X5 Retail Group', 'MISX', datetime('now')),
('ETLN', 'Эталон', 'MISX', datetime('now')),
('AQUA', 'Инарктика', 'MISX', datetime('now'));
