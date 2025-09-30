# 🚀 SamBot 2.0

**Микросервисная архитектура** YouTube-бота для резюмирования с поддержкой **RAG** (Retrieval-Augmented Generation) и **Docker Model Runner**.

> Миграция из монолитного SamBot v1 на современную микросервисную архитектуру с PostgreSQL + pgvector.

---

## 📋 Содержание

- [Архитектура](#-архитектура)
- [Технологический стек](#-технологический-стек)
- [Быстрый старт](#-быстрый-старт)
- [Миграция данных](#-миграция-данных)
- [Структура проекта](#-структура-проекта)
- [Разработка](#-разработка)

---

## 🏗 Архитектура

```
┌──────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   PostgreSQL     │    │  Docker Model    │    │   Web Monitor   │
│   + pgvector     │◄──►│     Runner       │◄──►│      UI         │
│                  │    │  (embeddings +   │    └─────────────────┘
│ • original_content│    │   chat)          │              ▲
│ • content_chunks │    │                  │              │
│ • embeddings     │    │ Models:          │              │
│ • summaries_cache│    │ • qwen2.5:3B     │    ┌─────────────────┐
└──────────────────┘    └──────────────────┘    │   Telegram      │
         ▲                        ▲             │     Bot         │
         │                        │             │   (будущее)     │
         │                        │             └─────────────────┘
┌──────────────────┐    ┌──────────────────┐
│   YouTube        │    │     Redis        │
│   Extractor      │◄──►│     Queue        │
│   Service        │    │                  │
└──────────────────┘    └──────────────────┘
```

---

## 🛠 Технологический стек

### Инфраструктура
- **Docker** + **Docker Compose** - контейнеризация
- **Docker Model Runner** - локальный AI (встроен в Docker Desktop 4.40+)

### База данных
- **PostgreSQL 16** - основная база данных
- **pgvector** - расширение для хранения embeddings

### AI модели
- **Chat**: `ai/qwen2.5:3B-Q4_K_M` или `ai/qwen2.5:7B-Q4_K_M`
- **Embeddings**: через Docker Model Runner API
- **Векторный поиск**: pgvector с cosine similarity

### Backend
- **FastAPI** - веб-сервисы
- **asyncpg** - PostgreSQL драйвер
- **aiohttp** - асинхронные HTTP запросы

### Очереди и кэш
- **Redis** - очереди задач

---

## 🚀 Быстрый старт

### Требования

- Docker Desktop 4.40+ с **Docker Model Runner**
- Python 3.11+
- 8+ GB RAM (для модели `qwen2.5:3B`)

### 1. Настройка Docker Model Runner

```bash
# Включить Model Runner с TCP доступом
docker desktop enable model-runner --tcp 12434

# Загрузить модель
docker model pull ai/qwen2.5:3B-Q4_K_M

# Проверить доступность
curl http://localhost:12434/health
```

### 2. Клонирование и настройка

```bash
# Перейти в директорию sambot-v2
cd sambot-v2

# Скопировать шаблон конфигурации
cp .env.example .env

# Отредактировать .env (установить DB_PASSWORD и другие параметры)
nano .env
```

### 3. Запуск сервисов

```bash
# Запустить PostgreSQL + Redis
docker-compose up -d postgres redis

# Проверить статус
docker-compose ps

# Посмотреть логи
docker-compose logs -f postgres
```

### 4. Проверка базы данных

```bash
# Подключиться к PostgreSQL
docker exec -it sambot_v2_postgres psql -U sambot -d sambot_v2

# Проверить таблицы
\dt

# Проверить pgvector
SELECT * FROM pg_extension WHERE extname = 'vector';

# Выход
\q
```

---

## 📦 Миграция данных

### Миграция из SamBot v1 (SQLite → PostgreSQL)

```bash
# Установить зависимости для миграции
pip install asyncpg aiosqlite

# Запустить миграцию
python scripts/migrate_from_sqlite.py \
  --sqlite-path ../SamBot/database/sambot.db \
  --postgres-url postgresql://sambot:PASSWORD@localhost:5432/sambot_v2

# Проверить результаты
docker exec -it sambot_v2_postgres psql -U sambot -d sambot_v2 -c "SELECT COUNT(*) FROM users;"
docker exec -it sambot_v2_postgres psql -U sambot -d sambot_v2 -c "SELECT COUNT(*) FROM original_content;"
```

---

## 📁 Структура проекта

```
sambot-v2/
├── docker-compose.yml         # Оркестрация сервисов
├── .env.example               # Шаблон конфигурации
├── README.md                  # Эта документация
│
├── migrations/                # SQL миграции
│   ├── 01_init_schema.sql    # Основные таблицы
│   └── 02_rag_tables.sql     # Таблицы для RAG
│
├── services/                  # Микросервисы
│   ├── youtube_extractor/    # YouTube extraction service
│   ├── ai_service/           # AI service (Docker Model Runner)
│   └── web_monitor/          # Web UI для мониторинга
│
├── scripts/                   # Утилиты
│   └── migrate_from_sqlite.py # Скрипт миграции из SQLite
│
└── docs/                      # Документация
```

---

## 🔧 Разработка

### Запуск отдельных сервисов

```bash
# Только база данных
docker-compose up -d postgres

# База данных + Redis
docker-compose up -d postgres redis

# Все сервисы
docker-compose up -d

# Просмотр логов
docker-compose logs -f service_name

# Остановка
docker-compose down

# Остановка с удалением volumes (ОСТОРОЖНО!)
docker-compose down -v
```

### Подключение к базе данных

```bash
# Через psql в контейнере
docker exec -it sambot_v2_postgres psql -U sambot -d sambot_v2

# Через pgAdmin или другой клиент
Host: localhost
Port: 5432
Database: sambot_v2
User: sambot
Password: (из .env файла)
```

### Работа с Redis

```bash
# Подключиться к Redis CLI
docker exec -it sambot_v2_redis redis-cli

# Проверить ключи
KEYS *

# Очистить все данные (ОСТОРОЖНО!)
FLUSHALL
```

---

## 🎯 Фазы разработки

### ✅ Фаза 1: База данных (завершена)
- [x] PostgreSQL + pgvector в Docker
- [x] Миграция схемы из SQLite
- [x] Таблицы для RAG системы
- [x] Скрипт миграции данных

### 🚧 Фаза 2: YouTube Extraction Service (в разработке)
- [ ] FastAPI service
- [ ] YouTube API интеграция
- [ ] Chunking для длинных видео
- [ ] Background tasks

### 📋 Фаза 3: AI Service
- [ ] Docker Model Runner wrapper
- [ ] Embeddings generation
- [ ] RAG retrieval logic
- [ ] Summary generation

### 📋 Фаза 4: Web Monitor UI
- [ ] FastAPI + Jinja2
- [ ] Dashboard со статистикой
- [ ] Content browser
- [ ] Error logs viewer

### 📋 Фаза 5: Telegram Bot Integration
- [ ] aiogram 3.x integration
- [ ] Message handlers
- [ ] State management
- [ ] User settings

---

## 📊 RAG Система

### Архитектура RAG

1. **Chunking**: Разбиение длинного контента на чанки (500-1000 токенов)
2. **Embeddings**: Генерация векторов через Docker Model Runner
3. **Vector Search**: Поиск похожих чанков через pgvector
4. **Context Retrieval**: Получение релевантного контекста
5. **Summary Generation**: Генерация резюме с использованием RAG

### Использование RAG

```sql
-- Найти похожие чанки по запросу
SELECT * FROM find_similar_chunks(
    query_embedding := '[0.1, 0.2, ...]'::vector(1536),
    target_content_id := 123,
    similarity_threshold := 0.7,
    max_results := 5
);

-- Статистика RAG системы
SELECT * FROM rag_stats;
```

---

## 🔍 Мониторинг

### Проверка здоровья сервисов

```bash
# PostgreSQL
docker exec sambot_v2_postgres pg_isready -U sambot

# Redis
docker exec sambot_v2_redis redis-cli ping

# Docker Model Runner
curl http://localhost:12434/health
```

### Логи

```bash
# Все сервисы
docker-compose logs -f

# Конкретный сервис
docker-compose logs -f postgres

# Последние 100 строк
docker-compose logs --tail=100 postgres
```

---

## 🐛 Решение проблем

### PostgreSQL не запускается

```bash
# Проверить логи
docker-compose logs postgres

# Пересоздать volume
docker-compose down -v
docker-compose up -d postgres
```

### Docker Model Runner недоступен

```bash
# Проверить статус
docker desktop status

# Включить Model Runner
docker desktop enable model-runner --tcp 12434

# Перезапустить Docker Desktop
```

### Ошибка подключения к базе

```bash
# Проверить переменные окружения
cat .env | grep DB_PASSWORD

# Проверить доступность PostgreSQL
docker exec -it sambot_v2_postgres psql -U sambot -d sambot_v2 -c "SELECT 1;"
```

---

## 📝 Полезные команды

```bash
# Создать backup базы данных
docker exec sambot_v2_postgres pg_dump -U sambot sambot_v2 > backup.sql

# Восстановить из backup
docker exec -i sambot_v2_postgres psql -U sambot -d sambot_v2 < backup.sql

# Пересоздать все volume (ОСТОРОЖНО!)
docker-compose down -v && docker-compose up -d

# Просмотр использования ресурсов
docker stats
```

---

## 📚 Дополнительная документация

- [Docker Model Runner Setup](../SamBot/DOCKER_MODEL_RUNNER_SETUP.md)
- [PostgreSQL + pgvector](https://github.com/pgvector/pgvector)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)

---

## 🤝 Вклад в проект

Этот проект находится в активной разработке. Каждая фаза разрабатывается последовательно с тщательным тестированием.

---

## 📄 Лицензия

MIT License

---

**Статус:** 🚧 В разработке (Фаза 1 завершена)

**Последнее обновление:** 29 сентября 2025