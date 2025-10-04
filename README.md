# Radar News Aggregator

Система агрегации новостей о компаниях из различных источников: поисковых систем (Google, Yandex, Serper) и социальных сетей (Twitter, Telegram).

## Возможности

- **Многоисточниковый сбор**: Google, Yandex, Serper, Twitter, Telegram
- **Полный текст статей**: Извлечение полного контента с сайтов
- **Фильтрация по доменам**: Поиск только на указанных сайтах
- **Дедупликация**: Автоматическое удаление дубликатов
- **Фильтрация по датам**: Сбор и поиск новостей за период
- **Оценка релевантности**: Автоматический расчет релевантности
- **REST API**: FastAPI с полной документацией

## Установка

### 1. Клонирование репозитория
```bash
git clone <repository-url>
cd radar
```

### 2. Создание виртуальной среды
```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
```

### 3. Установка зависимостей
```bash
pip install -r requirements.txt
```

### 4. Настройка переменных окружения
Создайте файл `.env` на основе `.env.example`:

```env
# Search APIs
GOOGLE_API_KEY=your_google_api_key
GOOGLE_CSE_ID=your_custom_search_engine_id
YANDEX_API_KEY=your_yandex_api_key
SERPER_API_KEY=your_serper_api_key

# Social Media
TWITTER_BEARER_TOKEN=your_twitter_bearer_token
TELEGRAM_API_ID=your_telegram_api_id
TELEGRAM_API_HASH=your_telegram_api_hash
TELEGRAM_PHONE=your_phone_number

# Configuration
MAX_RESULTS_PER_SOURCE=50
MAX_RETRIES=3
RETRY_DELAY=2
FETCH_FULL_ARTICLE_CONTENT=true

# Domain filtering (optional)
PREFERRED_NEWS_DOMAINS=rbc.ru,kommersant.ru,vedomosti.ru

# Twitter accounts filtering (optional)
TWITTER_ACCOUNTS=Reuters,BBCBreaking,CNNBusiness

# Telegram channels (optional)
TELEGRAM_CHANNELS=channel1,channel2
```

## Запуск

### Запуск API сервера
```bash
python main.py
```

API доступен по адресу: `http://localhost:8000`

Документация Swagger: `http://localhost:8000/docs`

## API Endpoints

### Health & Info
- `GET /` - Информация об API
- `GET /health` - Проверка работоспособности
- `GET /api/sources` - Список доступных источников

### Сбор новостей
```http
POST /api/collect
Content-Type: application/json

{
  "company_name": "Tesla",
  "max_results_per_source": 30,
  "use_search": true,
  "use_social": false,
  "save_to_db": true,
  "start_date": "2025-01-01T00:00:00Z",
  "end_date": "2025-02-01T00:00:00Z"
}
```

### Получение новостей
```http
GET /api/news/{company_name}?start_date=2025-01-01T00:00:00Z&end_date=2025-02-01T00:00:00Z&limit=100
```

### Статистика
```http
GET /api/stats/{company_name}
```

## Структура проекта

```
radar/
├── src/
│   ├── core/
│   │   ├── config.py          # Конфигурация
│   │   └── database.py        # Работа с БД
│   ├── models/
│   │   └── news.py            # Модели данных
│   ├── services/
│   │   ├── aggregator.py      # Основной агрегатор
│   │   ├── logging_service.py # Логирование
│   │   ├── search/            # Поисковые сервисы
│   │   │   ├── base.py
│   │   │   ├── google_search.py
│   │   │   ├── yandex_search.py
│   │   │   └── serper_search.py
│   │   └── social/            # Социальные сети
│   │       ├── telegram_parser.py
│   │       └── twitter_parser.py
│   └── utils/
│       ├── deduplication.py   # Дедупликация
│       └── text_processing.py # Обработка текста
├── migrations/                # Миграции БД
├── logs/                      # Логи
├── test/                      # Тесты
├── main.py                    # FastAPI приложение
├── requirements.txt
└── README.md
```

## Особенности

### Полный текст статей
Система автоматически извлекает полный текст статей с веб-страниц используя BeautifulSoup.

### Фильтрация по доменам
Укажите предпочтительные домены в `PREFERRED_NEWS_DOMAINS`:
```env
PREFERRED_NEWS_DOMAINS=rbc.ru,kommersant.ru,vedomosti.ru,tass.ru
```

### Фильтрация Twitter аккаунтов
Парсинг только определенных аккаунтов:
```env
TWITTER_ACCOUNTS=Reuters,BBCBreaking,CNNBusiness
```

### Механизм повторных попыток
При ошибках автоматически выполняются повторные попытки с exponential backoff:
- MAX_RETRIES=3
- RETRY_DELAY=2 (секунды)

### Очистка текста
Автоматическое удаление:
- HTML entities (&amp;, &quot;)
- Спецсимволов
- Zero-width characters
- Нормализация кавычек и тире

### Парсинг дат
Поддержка множества форматов:
- ISO 8601
- Русские форматы ("15 января 2024")
- Относительные даты
- HTML meta теги

## База данных

SQLite база данных `radar_news.db` создается автоматически при первом запуске.

### Таблицы
- `companies` - Компании
- `sources` - Источники
- `news` - Новости с дедупликацией по URL

## Разработка

### Запуск тестов
```bash
pytest test/
```

### Миграции
Файлы миграций в папке `/migrations`. Выполнение вручную.

## Логирование

Логи сохраняются в `/logs` с ротацией по дням.

## Лицензия

Проект для внутреннего использования.
