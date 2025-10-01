# Telegram Web App Setup

## Что сделано

✅ **Создан Telegram Web App** с real-time streaming интерфейсом:

1. **Server-Sent Events (SSE)** для live-логов извлечения
2. **Streaming суммаризация** (progressive text display)
3. **Telegram UI/UX** стиль с MainButton, HapticFeedback
4. **faster-whisper** для 4x ускорения транскрипции
5. **Qwen 2.5 7B** для структурированных конспектов

## Локальный тест

Web UI доступен по адресу:
```
http://localhost:8080
```

Откройте в браузере чтобы протестировать интерфейс.

## Развертывание в Telegram Bot

### 1. Создайте Telegram бота

Напишите [@BotFather](https://t.me/botfather):
```
/newbot
```

Следуйте инструкциям, получите **API Token**.

### 2. Создайте Web App

В диалоге с BotFather:
```
/newapp
```

Выберите вашего бота, введите:
- **Short name**: `sambot`
- **Title**: `SamBot - AI Video Analysis`
- **Description**: `Extract, transcribe and summarize YouTube videos with AI`
- **URL**: `https://your-domain.com` (замените на ваш URL)
- **Image**: загрузите иконку 640x360px

### 3. Настройте публичный URL

Вам нужен публичный HTTPS URL для Web App. Варианты:

#### A) ngrok (для тестирования)
```bash
ngrok http 8080
```

Скопируйте HTTPS URL (например, `https://abc123.ngrok.io`).

#### B) Cloudflare Tunnel (бесплатно)
```bash
cloudflared tunnel --url http://localhost:8080
```

#### C) Railway / Fly.io / VPS

Разверните Docker Compose на облачном сервере с публичным IP.

### 4. Обновите URL в BotFather

```
/editapp
```

Выберите ваш app → **Edit URL** → вставьте ваш HTTPS URL.

### 5. Добавьте кнопку в бота

Создайте Telegram бота с помощью Python SDK:

```python
from telegram import Update, WebAppInfo, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[
        KeyboardButton(
            "🤖 Анализ видео",
            web_app=WebAppInfo(url="https://your-domain.com")
        )
    ]]

    await update.message.reply_text(
        "Нажмите кнопку ниже чтобы открыть SamBot:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

app = Application.builder().token("YOUR_BOT_TOKEN").build()
app.add_handler(CommandHandler("start", start))
app.run_polling()
```

### 6. Готово!

Откройте бота в Telegram → `/start` → нажмите кнопку "🤖 Анализ видео".

Web App откроется внутри Telegram с нативным UI!

## Возможности Web App

- ✅ **Вставка URL** из буфера обмена
- ✅ **Real-time progress** показывает что процесс не висит
- ✅ **MainButton** для действий (как в Telegram Premium apps)
- ✅ **HapticFeedback** для тактильных ощущений
- ✅ **Адаптивный UI** под темную/светлую тему Telegram
- ✅ **Streaming summary** прогрессивное отображение текста

## Демо API

Все endpoints доступны для прямых API вызовов:

- `POST /extract/stream` - SSE stream извлечения
- `POST /summarize/stream/{content_id}` - SSE stream суммаризации
- `GET /summary/{content_id}` - получить готовый summary
- `POST /rag/ask/stream` - RAG Q&A с контекстом

## Архитектура

```
Telegram Bot → Web App (iframe) → Flask SSE →
  ├─ Extractor (faster-whisper)
  ├─ Summarizer (Qwen 7B)
  └─ RAG Service (nomic-embed + pgvector)
```

## Следующие шаги

1. **Автоматизация**: Worker автоматически создает embedding после extraction
2. **Batch processing**: Обработка старых видео без embeddings
3. **Телеграм-бот**: Прямая отправка ссылок в чат → автоматический анализ
4. **Кэширование**: Redis кэш для частых запросов
5. **Оптимизация**: Streaming через Ollama API (true token-by-token)

## Технические детали

**Frontend:**
- Telegram Web App SDK
- Server-Sent Events (SSE)
- Vanilla JS (без framework)

**Backend:**
- Flask с `stream_with_context`
- faster-whisper (4x speed vs vanilla)
- Ollama (Qwen 2.5 7B)
- pgvector для semantic search

**Инфраструктура:**
- Docker Compose
- PostgreSQL + pgvector extension
- Redis для background jobs
