# 🎥 SamBot v2 - YouTube Content Processor

> **Превращай YouTube видео в структурированные конспекты с AI**

Больше не нужно тратить часы на просмотр длинных видео. SamBot извлекает транскрипты, создаёт подробные резюме с помощью AI и позволяет задавать вопросы по содержанию через семантический поиск.

**🚀 Быстро.** Субтитры извлекаются за секунды. AI summary генерируется в реальном времени с streaming.

**💰 Дёшево.** DeepSeek API стоит копейки (~$0.0003 за видео). Или используй бесплатный Ollama локально.

**🎯 Качество.** Структурированные конспекты с emoji, markdown и ключевыми выводами. RAG система для точных ответов на вопросы.

## 🎯 Что умеет (реально работает)

- ✅ **Извлечение контента** из YouTube видео (субтитры + Whisper для аудио)
- ✅ **AI резюмирование** через DeepSeek API или локальный Ollama
- ✅ **RAG (Retrieval-Augmented Generation)** - семантический поиск и Q&A по видео
- ✅ **Streaming UI** - real-time отображение прогресса extraction и summary
- ✅ **Background processing** - автоматическое создание embeddings
- ✅ **PostgreSQL + pgvector** - хранение транскриптов и векторов

## 🚧 В разработке

- 🔄 **Telegram Bot** - будет добавлен как основной интерфейс
- 🔄 **Web UI улучшения** - текущий UI базовый, планируется улучшение

## 🏗 Архитектура

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Content        │────▶│  PostgreSQL      │◄────│  RAG Service    │
│  Extractor      │     │  + pgvector      │     │  (Semantic      │
│  (YouTube API + │     │                  │     │   Search)       │
│   Whisper)      │     │  • Transcripts   │     └─────────────────┘
└─────────────────┘     │  • Chunks        │              │
                        │  • Embeddings    │              │
┌─────────────────┐     │  • Summaries     │              │
│  Summarizer     │────▶│                  │              │
│  (DeepSeek/     │     └──────────────────┘              │
│   Ollama)       │              │                         │
└─────────────────┘              │                         │
        │                        │                         │
        │                        ▼                         │
        │              ┌──────────────────┐                │
        └─────────────▶│   Web UI         │◄───────────────┘
                       │   (Streaming)    │
                       └──────────────────┘
                                │
                       ┌──────────────────┐
                       │  Telegram Bot    │
                       │  (Planned)       │
                       └──────────────────┘
```

## 🛠 Технологии

**Backend:**
- Python 3.11 + FastAPI
- PostgreSQL 16 + pgvector (векторная БД)
- Redis + RQ (фоновые задачи)

**AI:**
- DeepSeek API (236B модель, streaming)
- Ollama (локальная альтернатива, qwen2.5:7b/14b/32b)
- nomic-embed-text (embeddings)

**Extraction:**
- yt-dlp (YouTube субтитры)
- faster-whisper (транскрибация аудио)
- YouTube Data API v3 (метаданные)

## 🚀 Быстрый старт

### Требования

- Docker + Docker Compose
- 8+ GB RAM
- DeepSeek API key или Ollama

### 1. Клонирование

```bash
git clone https://github.com/gagarinyury/SamBot.git
cd SamBot
```

### 2. Настройка

```bash
# Скопировать конфиг
cp .env.example .env

# Отредактировать .env
nano .env
```

Минимальная конфигурация `.env`:

```bash
# Database
DB_PASSWORD=your_secure_password

# YouTube API (опционально, для метаданных)
YOUTUBE_API_KEY=your_youtube_api_key

# AI Provider: deepseek или ollama
AI_PROVIDER=deepseek

# DeepSeek API (если AI_PROVIDER=deepseek)
DEEPSEEK_API_KEY=sk-your-deepseek-key

# Ollama модель (если AI_PROVIDER=ollama)
SUMMARIZER_MODEL=qwen2.5:7b-instruct-q4_K_M
```

### 3. Для Ollama (если не используете DeepSeek)

```bash
# Установить Ollama
brew install ollama  # macOS
# или скачать с https://ollama.com

# Запустить Ollama
ollama serve

# Загрузить модели
ollama pull qwen2.5:7b-instruct-q4_K_M  # 5GB RAM
ollama pull nomic-embed-text            # embeddings
```

### 4. Запуск

```bash
# Запустить все сервисы
docker compose up -d

# Проверить статус
docker compose ps

# Посмотреть логи
docker compose logs -f
```

### 5. Использование

Открыть Web UI: http://localhost:8080

1. Вставить YouTube URL
2. Нажать "Extract Content"
3. Дождаться extraction (1-2 мин для аудио, 5-10 сек для субтитров)
4. Нажать "Create Summary" для резюмирования
5. Задать вопросы в RAG Q&A секции

## 📦 Сервисы

| Сервис | Порт | Описание |
|--------|------|----------|
| **web_ui** | 8080 | Web интерфейс (streaming) |
| **content_extractor** | 8001 | Extraction YouTube контента |
| **summarizer** | 8002 | AI резюмирование (DeepSeek/Ollama) |
| **rag_service** | 8003 | Семантический поиск + Q&A |
| **postgres** | 5432 | База данных + pgvector |
| **redis** | 6379 | Очереди задач |
| **worker** | - | Background processor (embeddings) |

## 🎨 Возможности

### 1. Content Extraction

**Стратегии извлечения:**
1. YouTube субтитры (быстро, ~5 сек)
2. Whisper transcription (медленно, 1-2 мин, высокое качество)

**Что извлекается:**
- Транскрипт (чистый текст, без WEBVTT мусора)
- Метаданные (название, канал, длительность, описание)
- Главы видео (если есть в описании)

### 2. AI Summarization

**Два режима:**

**A) DeepSeek API (рекомендуется):**
- ✅ Быстро (~2-5 сек start, streaming)
- ✅ Топ качество (236B параметров)
- ✅ Дёшево (~$0.0001-0.0003 за summary)
- ✅ Структурированный формат (emoji, markdown)

**B) Ollama (локально):**
- ✅ Бесплатно
- ✅ Приватность
- ⚠️ Медленнее (30-60 сек для 7B модели)
- ⚠️ Требует RAM (5GB для 7B, 9GB для 14B, 20GB для 32B)

**Формат summary:**
```markdown
## 🎯 ГЛАВНАЯ ТЕМА
[Одно предложение]

## 📋 КРАТКИЙ ОБЗОР
[2-3 предложения]

## 🔑 ОСНОВНЫЕ РАЗДЕЛЫ
### 1. [Раздел]
- **Ключевая мысль**: ...
- **Детали**: ...
- **Почему важно**: ...

## 💡 КЛЮЧЕВЫЕ ВЫВОДЫ
1. ...
2. ...

## 📊 ВАЖНЫЕ ФАКТЫ И ЦИФРЫ
- ...
```

### 3. RAG (Semantic Search + Q&A)

**Как работает:**
1. Транскрипт разбивается на чанки (~500 токенов)
2. Для каждого чанка создаётся embedding (768-мерный вектор)
3. При вопросе — поиск похожих чанков через pgvector
4. LLM генерирует ответ на основе найденного контекста

**Параметры:**
- `SIMILARITY_THRESHOLD`: 0.5 (cosine similarity)
- `TOP_K_RESULTS`: 3 (кол-во чанков для контекста)
- `content_id` фильтр: поиск только по конкретному видео

## ⚙️ Конфигурация

### Переключение AI провайдера

```bash
# На DeepSeek
echo "AI_PROVIDER=deepseek" >> .env
docker compose restart summarizer rag_service

# На Ollama
echo "AI_PROVIDER=ollama" >> .env
docker compose restart summarizer rag_service
```

### Выбор модели Ollama

```bash
# Скачать модель
ollama pull qwen2.5:14b  # 9GB RAM, лучше качество

# Обновить конфиг
echo "SUMMARIZER_MODEL=qwen2.5:14b" >> .env
docker compose restart summarizer
```

**Доступные модели:**
- `qwen2.5:3b` (~2GB RAM, базовое качество)
- `qwen2.5:7b` (~5GB RAM, хорошее качество) ⭐ рекомендуется
- `qwen2.5:14b` (~9GB RAM, отличное качество)
- `qwen2.5:32b` (~20GB RAM, максимальное качество)

### Изменение промптов

Промпты находятся в коде:
- **Summarizer**: `services/summarizer/summarizer.py` (SYSTEM_PROMPT)
- **RAG**: `services/rag_service/rag_engine.py` (RAG_SYSTEM_PROMPT)

После изменения:
```bash
docker compose up -d --build summarizer  # или rag_service
```

## 🐛 Решение проблем

### Extraction не работает

```bash
# Проверить логи
docker compose logs content_extractor

# Частые причины:
# - YouTube заблокировал IP → добавить cookies.txt
# - Нет субтитров → будет использован Whisper (медленно)
# - YouTube API key отсутствует → метаданные через yt-dlp
```

### Summary не генерируется

```bash
# Проверить AI провайдер
docker compose logs summarizer

# DeepSeek:
# - Проверить API key в .env
# - Проверить лимиты на platform.deepseek.com

# Ollama:
# - Проверить что Ollama запущен: ollama list
# - Проверить что модель загружена
```

### RAG не находит результаты

```bash
# Проверить embeddings
docker compose exec postgres psql -U sambot -d sambot_v2 \
  -c "SELECT COUNT(*) FROM content_embeddings;"

# Если embeddings = 0:
# - Worker не создал embeddings
# - Проверить: docker compose logs worker
```

### Streaming показывает "Generating..." бесконечно

```bash
# Проверить логи summarizer
docker compose logs summarizer --tail 50

# Частые причины:
# - DeepSeek API недоступен
# - Ollama не отвечает
# - Превышен timeout (90 сек)

# Решение: обновить страницу и попробовать снова
```

## 📁 Структура проекта

```
sambot-v2/
├── docker-compose.yml              # Оркестрация сервисов
├── .env                            # Конфигурация (не в git)
├── .env.example                    # Шаблон конфигурации
├── README.md                       # Эта документация
│
├── migrations/                     # SQL миграции
│   ├── 01_init_schema.sql         # Основные таблицы
│   └── 02_rag_tables.sql          # Таблицы для RAG
│
├── services/
│   ├── content_extractor/         # YouTube extraction
│   │   ├── main.py               # FastAPI app
│   │   ├── extractor.py          # Логика extraction
│   │   └── config.py             # Настройки
│   │
│   ├── summarizer/                # AI summarization
│   │   ├── main.py               # FastAPI app
│   │   ├── summarizer.py         # Логика summary
│   │   ├── deepseek_client.py    # DeepSeek API
│   │   └── ollama_client.py      # Ollama API
│   │
│   ├── rag_service/               # Semantic search + Q&A
│   │   ├── main.py               # FastAPI app
│   │   ├── rag_engine.py         # RAG логика
│   │   └── database.py           # Vector search
│   │
│   ├── web_ui/                    # Web интерфейс
│   │   ├── app_streaming.py      # Flask app (SSE)
│   │   └── templates/            # HTML templates
│   │
│   └── worker/                    # Background tasks
│       ├── worker.py             # RQ worker
│       └── tasks.py              # Task definitions
│
└── scripts/                       # Утилиты
    └── migrate_from_sqlite.py    # Миграция из v1
```

## 📊 База данных

**Таблицы:**
- `users` - пользователи
- `original_content` - транскрипты видео
- `content_chunks` - разбитые чанки для RAG
- `content_embeddings` - векторы (pgvector)
- `summaries_cache` - кэш резюме

**Полезные запросы:**

```sql
-- Статистика
SELECT COUNT(*) FROM original_content;
SELECT COUNT(*) FROM content_embeddings;

-- Последние видео
SELECT id, original_url, LENGTH(raw_content)
FROM original_content
ORDER BY created_at DESC
LIMIT 5;

-- Semantic search (пример)
SELECT chunk_text,
       1 - (embedding <=> '[0.1,0.2,...]'::vector) as similarity
FROM content_embeddings ce
JOIN content_chunks cc ON ce.chunk_id = cc.id
WHERE 1 - (embedding <=> '[0.1,0.2,...]'::vector) >= 0.5
ORDER BY embedding <=> '[0.1,0.2,...]'::vector
LIMIT 5;
```

## 🔐 Безопасность

**Что НЕ коммитится в git:**
- `.env` - содержит пароли и API ключи
- `cookies.txt` - YouTube cookies (если используются)
- `audio_storage/` - скачанные аудио файлы
- `__pycache__/` - Python кэш

**Рекомендации:**
- Используй сильный `DB_PASSWORD`
- DeepSeek API key держи в секрете
- YouTube API key имеет квоты — не публикуй

## 📈 Производительность

**Типичное время обработки:**

| Операция | Время | Примечание |
|----------|-------|------------|
| Extraction (subtitles) | 5-10 сек | Быстро |
| Extraction (Whisper) | 1-2 мин | Зависит от длины видео |
| Embeddings creation | 10-30 сек | Background, автоматически |
| Summary (DeepSeek) | 5-15 сек | Streaming, видишь прогресс |
| Summary (Ollama 7B) | 30-60 сек | Локально, медленнее |
| RAG Q&A | 2-5 сек | Быстрый поиск + LLM |

**Стоимость (DeepSeek):**
- Summary: ~$0.0001-0.0003 за видео
- RAG Q&A: ~$0.00005 за вопрос
- 1000 видео ≈ $0.20-0.30

## 🚀 Дальнейшее развитие

**Запланировано:**
1. **Telegram Bot** - основной интерфейс
2. **Улучшенный Web UI** - более красивый и удобный
3. **Batch processing** - обработка нескольких видео
4. **Export** - Notion, Obsidian, Markdown
5. **Multi-language support** - интерфейс на русском/английском

## 📚 Полезные ссылки

- [DeepSeek Platform](https://platform.deepseek.com)
- [Ollama](https://ollama.com)
- [pgvector](https://github.com/pgvector/pgvector)
- [FastAPI](https://fastapi.tiangolo.com)
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)

## 🤝 Contributing

Проект в активной разработке. Pull requests приветствуются!

## 📄 Лицензия

MIT

---

**Статус:** ✅ Работает (основные фичи)
**Последнее обновление:** 1 октября 2025
