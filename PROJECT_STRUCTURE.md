# 📁 SamBot 2.0 - Project Structure

**Версия:** 2.0
**Дата:** 30 сентября 2025
**Статус:** Phase 2 Complete (Content Extractor) - Clean Build

---

## 🌳 Структура проекта

```
sambot-v2/
├── migrations/                     # База данных
│   ├── 01_init_schema.sql         # Основные таблицы (16 tables)
│   └── 02_rag_tables.sql          # RAG система (chunks, embeddings)
│
├── scripts/                        # Утилиты
│   └── migrate_from_sqlite.py     # Миграция из SamBot v1
│
├── services/                       # Микросервисы
│   └── content_extractor/         # YouTube extraction service
│       ├── chunking/              # Chunking strategies
│       │   ├── __init__.py
│       │   ├── chapter_based.py   # Chunking по главам видео
│       │   └── fixed_size.py      # Chunking по токенам (500)
│       │
│       ├── database/              # Data access layer
│       │   ├── __init__.py
│       │   ├── connection.py      # AsyncPG connection pool
│       │   └── repository.py      # Content/chunks storage
│       │
│       ├── extractors/            # YouTube extractors
│       │   ├── __init__.py
│       │   ├── chapters.py        # Парсинг глав из описания
│       │   └── youtube.py         # YouTube transcript API
│       │
│       ├── utils/                 # Utilities
│       │   ├── __init__.py
│       │   └── rate_limiter.py    # Rate limiting (1 req/min)
│       │
│       ├── .dockerignore          # Docker ignore rules
│       ├── Dockerfile             # Python 3.11-slim image
│       ├── README.md              # Service documentation
│       ├── main.py                # FastAPI application
│       └── requirements.txt       # Service dependencies
│
├── .env.example                    # Environment variables template
├── .gitignore                      # Git ignore rules
├── Makefile                        # Development commands
├── PROJECT_STRUCTURE.md            # Документация структуры проекта (этот файл)
├── README.md                       # Главная документация
├── docker-compose.yml              # Docker services setup
└── requirements.txt                # Root dependencies

9 directories, 26 files
```

---

## 📦 Компоненты системы

### 1. **База данных (PostgreSQL 16 + pgvector)**

**Основные таблицы:**
- `users` - Пользователи Telegram
- `subscription_plans` - Планы подписок
- `usage_stats` - Статистика использования
- `original_content` - Исходный контент (YouTube видео)
- `summaries_cache` - Кэш резюме
- `prompt_templates` - Шаблоны промптов
- `translations` - i18n переводы
- `supported_languages` - Поддерживаемые языки
- `bot_analytics` - Аналитика бота
- `error_logs` - Логи ошибок

**RAG таблицы:**
- `content_chunks` - Чанки контента с timestamps
- `content_embeddings` - Векторные embeddings (1536 dim)
- `chunking_strategies` - Стратегии разбиения
- `rag_queries` - Логи RAG запросов

**Функции:**
- `find_similar_chunks()` - Векторный поиск
- `cosine_similarity()` - Cosine similarity
- VIEW `rag_stats` - Статистика RAG

---

### 2. **Content Extractor Service (FastAPI)**

**Порт:** `8001` (host) → `8000` (container)

**Эндпоинты:**
- `POST /extract` - Извлечение YouTube контента
- `GET /content/{id}` - Получение контента с чанками
- `GET /health` - Health check

**Возможности:**
- YouTube transcript extraction (youtube_transcript_api)
- POT provider для обхода ограничений YouTube
- Chapter-based chunking (если есть главы)
- Fixed-size chunking (500 токенов)
- Хранение в PostgreSQL с metadata
- Rate limiting (1 видео/минуту)

**Request example:**
```json
{
  "url": "https://youtube.com/watch?v=...",
  "user_id": null,
  "language": "ru"
}
```

**Response example:**
```json
{
  "status": "success",
  "content_id": 1,
  "platform": "youtube",
  "extraction_method": "youtube_transcript_api",
  "metadata": {
    "title": "...",
    "channel": "...",
    "duration": 1465,
    "description": "полное описание",
    "language": "ru"
  },
  "chunking": {
    "strategy": "fixed_size_500",
    "total_chunks": 75
  },
  "processing_time": 8.2
}
```

---

### 3. **Docker Services**

**docker-compose.yml включает:**

| Сервис | Образ | Порты | Описание |
|--------|-------|-------|----------|
| `postgres` | pgvector/pgvector:pg16 | 5432 | PostgreSQL + pgvector |
| `pot_provider` | brainicism/bgutil-ytdlp-pot-provider | 4416 | POT provider для YouTube |
| `content_extractor` | sambot-v2-content_extractor | 8001 | FastAPI extraction service |

**Network:** `sambot_network` (bridge)

---

## 🗂️ Описание ключевых файлов

### Конфигурация проекта

| Файл | Описание |
|------|----------|
| `docker-compose.yml` | Определение всех Docker сервисов и их конфигурация |
| `Makefile` | Команды для разработки (up, down, logs, psql, etc.) |
| `.env.example` | Шаблон переменных окружения |
| `.gitignore` | Правила игнорирования для Git |
| `requirements.txt` | Root-level зависимости Python |
| `README.md` | Главная документация проекта |
| `PROJECT_STRUCTURE.md` | Документация структуры проекта (этот файл) |

### База данных

| Файл | Строк | Описание |
|------|-------|----------|
| `migrations/01_init_schema.sql` | 257 | Основная схема: 16 таблиц + triggers + indexes |
| `migrations/02_rag_tables.sql` | 184 | RAG система: chunks, embeddings, functions |

### Скрипты

| Файл | Описание |
|------|----------|
| `scripts/migrate_from_sqlite.py` | Миграция данных из SamBot v1 (SQLite → PostgreSQL) |

### Content Extractor Service

**Главный модуль:**
- `main.py` (282 строки) - FastAPI app, endpoints, lifespan management

**Extractors:**
- `extractors/youtube.py` - YouTube transcript extraction (youtube_transcript_api + POT provider)
- `extractors/chapters.py` - Парсинг глав из описания видео

**Chunking:**
- `chunking/chapter_based.py` - Разбиение по главам
- `chunking/fixed_size.py` - Разбиение по токенам (500)

**Database:**
- `database/connection.py` - AsyncPG connection pool
- `database/repository.py` - Data access layer (store_content, store_chunks)

**Utils:**
- `utils/rate_limiter.py` - Rate limiting (1 req/min)

**Docker:**
- `Dockerfile` - Python 3.11-slim + dependencies
- `.dockerignore` - Правила для Docker build

---

## 🎯 Статус реализации

| Phase | Статус | Описание |
|-------|--------|----------|
| **Phase 1: Database** | ✅ Complete | PostgreSQL + pgvector, 16 таблиц, RAG ready |
| **Phase 2: Content Extractor** | ✅ Complete | YouTube extraction + chunking + storage |
| **Phase 3: AI Service** | 📋 Planned | Docker Model Runner integration, embeddings, RAG |
| **Phase 4: Web Monitor** | 📋 Planned | FastAPI + Jinja2 dashboard |
| **Phase 5: Telegram Bot** | 📋 Planned | aiogram 3.x integration |

---

## 🔧 Команды разработки

```bash
# Запуск всех сервисов
make up

# Запуск только БД
make up-db

# Остановка
make down

# Логи
make logs
make logs-db

# Подключение к PostgreSQL
make psql

# Backup/Restore
make backup
make restore FILE=backup.sql

# Миграция из v1
make migrate
```

---

## 📊 Технологии

**Backend:**
- FastAPI - Async REST API
- asyncpg - PostgreSQL async driver
- aiohttp - Async HTTP client

**Database:**
- PostgreSQL 16 - Relational database
- pgvector - Vector similarity search

**Infrastructure:**
- Docker & Docker Compose
- POT Provider (YouTube bypass)

**AI (Planned):**
- Docker Model Runner (qwen2.5:3B/7B)
- tiktoken - Token counting

**Future:**
- aiogram 3.x - Telegram bot framework
- Redis - Caching & queues

---

## 🔐 Environment Variables

```bash
# Database
DB_PASSWORD=...

# AI Models (Future)
MODEL_NAME=ai/qwen2.5:3B-Q4_K_M
EMBEDDING_MODEL=ai/qwen2.5:3B-Q4_K_M
EMBEDDING_DIMENSION=1536

# General
ENVIRONMENT=development
LOG_LEVEL=INFO
```

---

## 📝 Примечания

1. **Чистый проект** - удалены все устаревшие файлы, тестовые данные, пустые сервисы
2. **Минимальная структура** - 26 файлов, 9 директорий (без venv, cache, временных файлов)
3. **Production-ready** - Content Extractor готов к использованию
4. **RAG-ready** - База данных готова для embeddings и векторного поиска
5. **Документирован** - каждый компонент имеет описание и примеры

**Удалено при очистке:**
- Пустые placeholder-сервисы (youtube_extractor, ai_service, web_monitor)
- Временные документы разработки (DEPLOYMENT_REPORT, FIXES_APPLIED, RATE_LIMITS)
- Устаревшие инструкции (CLAUDE.md, LINUX_DEPLOYMENT_COOKIES)
- Неиспользуемые модули (youtube_api.py, routers/)
- Тестовые файлы и локальные данные

**Следующий шаг:** Phase 3 - AI Service с Docker Model Runner