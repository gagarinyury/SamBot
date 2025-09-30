# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**SamBot 2.0** - микросервисная архитектура YouTube-бота для резюмирования с поддержкой RAG (Retrieval-Augmented Generation) и Docker Model Runner. Миграция из монолитного SamBot v1 на современную архитектуру с PostgreSQL + pgvector.

## Technology Stack

- **Infrastructure**: Docker, Docker Compose, Docker Model Runner (встроен в Docker Desktop 4.40+)
- **Database**: PostgreSQL 16 с pgvector для хранения embeddings
- **Backend**: FastAPI, asyncpg, aiohttp
- **AI Models**: qwen2.5:3B или 7B через Docker Model Runner
- **Queue/Cache**: Redis
- **Future**: Telegram bot (aiogram 3.x)

## Common Commands

### Docker & Services
```bash
# Запуск всех сервисов
make up
# или: docker-compose up -d

# Запуск только БД и Redis
make up-db
# или: docker-compose up -d postgres redis

# Остановка сервисов
make down

# Просмотр логов
make logs              # все сервисы
make logs-db           # только PostgreSQL
docker-compose logs -f postgres

# Статус сервисов
make status
```

### Database Operations
```bash
# Подключение к PostgreSQL
make psql
# или: docker exec -it sambot_v2_postgres psql -U sambot -d sambot_v2

# Backup БД
make backup
# Результат: backup_YYYYMMDD_HHMMSS.sql

# Restore БД
make restore FILE=backup.sql

# Миграция из SQLite (SamBot v1)
make migrate
# или: python scripts/migrate_from_sqlite.py --sqlite-path ../SamBot/database/sambot.db
```

### Redis
```bash
# Подключение к Redis CLI
make redis
# или: docker exec -it sambot_v2_redis redis-cli
```

### Docker Model Runner
```bash
# Проверка статуса
make check-dmr
# или: curl http://localhost:12434/health

# Включение Model Runner с TCP
docker desktop enable model-runner --tcp 12434

# Загрузка модели
docker model pull ai/qwen2.5:3B-Q4_K_M
```

### Development
```bash
# Установка зависимостей
make install

# Форматирование кода
make format

# Линтинг
make lint

# Тесты
make test
```

## Architecture Overview

### Microservices Structure
```
├── services/
│   ├── youtube_extractor/  # YouTube extraction (FastAPI)
│   │   Port: 8001
│   │
│   ├── ai_service/         # AI wrapper для Docker Model Runner
│   │   Port: 8002
│   │   - Embeddings generation
│   │   - RAG retrieval logic
│   │   - Summary generation
│   │
│   └── web_monitor/        # Web UI (FastAPI + Jinja2)
│       Port: 8080
│       - Dashboard со статистикой
│       - Content browser
│       - Error logs viewer
```

### Database Schema

**Core Tables** (migrations/01_init_schema.sql):
- `users` - пользователи Telegram
- `subscription_plans` - планы подписок с мультивалютностью
- `daily_usage` - трекинг использования
- `original_content` - исходный контент (YouTube видео/статьи)
- `summaries_cache` - кэш резюме
- `error_logs` - логи ошибок

**RAG Tables** (migrations/02_rag_tables.sql):
- `content_chunks` - чанки контента (500-1000 токенов)
  - Поддержка timestamps для видео (start_timestamp, end_timestamp)
- `content_embeddings` - векторные embeddings через pgvector
  - vector(1536) для semantic search
  - cosine similarity через pgvector

**Key Functions**:
- `find_similar_chunks()` - векторный поиск похожих чанков
- `rag_stats` VIEW - статистика RAG системы

### RAG System Flow

1. **Chunking**: Разбиение длинного контента на чанки (500-1000 токенов)
2. **Embeddings**: Генерация векторов через Docker Model Runner
3. **Vector Search**: Поиск похожих чанков через pgvector (cosine similarity)
4. **Context Retrieval**: Получение релевантного контекста
5. **Summary Generation**: Генерация резюме с использованием RAG

### Docker Model Runner Integration

- **URL**: `http://model-runner.docker.internal/engines/v1` (внутри контейнеров)
- **Host URL**: `http://localhost:12434` (с хост-машины)
- **Models**:
  - Chat: `ai/qwen2.5:3B-Q4_K_M` или `ai/qwen2.5:7B-Q4_K_M`
  - Embeddings: через тот же model runner API
- **Требования**: Docker Desktop 4.40+ с включенным Model Runner

## Configuration

### Environment Variables (.env)
```bash
# Основные
DB_PASSWORD=...              # PostgreSQL пароль
MODEL_NAME=ai/qwen2.5:3B-Q4_K_M
EMBEDDING_MODEL=ai/qwen2.5:3B-Q4_K_M
EMBEDDING_DIMENSION=1536
ENVIRONMENT=development
LOG_LEVEL=INFO

# Будущее
# TELEGRAM_BOT_TOKEN=...
```

### Service URLs (внутри Docker network)
- PostgreSQL: `postgres:5432`
- Redis: `redis:6379`
- YouTube Extractor: `http://youtube_extractor:8000`
- AI Service: `http://ai_service:8000`
- Docker Model Runner: `http://model-runner.docker.internal/engines/v1`

### External Ports
- PostgreSQL: `localhost:5432`
- Redis: `localhost:6379`
- YouTube Extractor: `localhost:8001`
- AI Service: `localhost:8002`
- Web Monitor: `localhost:8080`
- Docker Model Runner: `localhost:12434`

## Development Status

**✅ Phase 1: Database (завершена)**
- PostgreSQL + pgvector в Docker
- Миграция схемы из SQLite
- Таблицы для RAG системы
- Скрипт миграции данных

**🚧 Phase 2: YouTube Extraction Service (в разработке)**
- FastAPI service (структура создана)
- YouTube API интеграция
- Chunking для длинных видео
- Background tasks

**📋 Phase 3: AI Service (планируется)**
- Docker Model Runner wrapper
- Embeddings generation
- RAG retrieval logic
- Summary generation

**📋 Phase 4: Web Monitor UI (планируется)**
- FastAPI + Jinja2
- Dashboard
- Content browser
- Error logs viewer

**📋 Phase 5: Telegram Bot Integration (будущее)**
- aiogram 3.x integration
- Message handlers
- State management
- User settings

## Key Implementation Notes

### When Working with Database
- Всегда используй `asyncpg` для PostgreSQL операций
- Vector embeddings используют `vector(1536)` тип данных
- pgvector индексы: `content_embeddings_embedding_idx` (HNSW для cosine)
- Chunking с поддержкой timestamps для навигации в видео

### When Working with AI Service
- Docker Model Runner использует OpenAI-compatible API
- Embeddings генерируются через ту же модель (`qwen2.5`)
- Всегда проверяй доступность Model Runner перед запуском: `curl http://localhost:12434/health`
- Используй `tiktoken` для подсчета токенов

### When Working with Services
- Все сервисы - FastAPI приложения
- Используй `structlog` для structured logging
- Healthchecks обязательны для всех сервисов
- Зависимости между сервисами через `depends_on` в docker-compose

### Migration from SamBot v1
- Используй `scripts/migrate_from_sqlite.py` для миграции данных
- Скрипт поддерживает инкрементальную миграцию
- Mapping старых таблиц на новую схему автоматический
- Всегда делай backup перед миграцией

## Troubleshooting

### PostgreSQL Issues
```bash
# Проверка логов
docker-compose logs postgres

# Пересоздание volume (ВНИМАНИЕ: удаляет данные)
docker-compose down -v
docker-compose up -d postgres
```

### Docker Model Runner Issues
```bash
# Проверка статуса
docker desktop status

# Включение Model Runner
docker desktop enable model-runner --tcp 12434

# Проверка доступности
curl http://localhost:12434/health
```

### Connection Issues
```bash
# Проверка .env
cat .env | grep DB_PASSWORD

# Проверка PostgreSQL доступности
docker exec -it sambot_v2_postgres psql -U sambot -d sambot_v2 -c "SELECT 1;"
```