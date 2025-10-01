# 🤖 Auto-Embedding Pipeline

Автоматическая обработка контента: Embedding + Structured Summary

## ✨ Что это?

После экстракции YouTube/Instagram видео **автоматически**:
1. 📊 Генерируется embedding (nomic-embed-text, 768-dim)
2. 📝 Создаётся структурированный конспект (Qwen 2.5 3B)

**Без ручных действий** — всё в фоне через Redis Queue!

---

## 🏗 Архитектура

```
┌─────────────┐
│ Extractor   │ → Redis Queue
└─────────────┘       ↓
                 ┌─────────┐
                 │ Worker  │ (background)
                 └─────────┘
                      ↓
         ┌────────────┴────────────┐
         │                         │
    ┌────────┐               ┌────────────┐
    │ RAG    │               │ Summarizer │
    │Service │               │  Service   │
    └────────┘               └────────────┘
         ↓                          ↓
    PostgreSQL                 PostgreSQL
    (embeddings)              (summaries)
```

---

## 🚀 Как использовать

### 1. Экстракция триггерит pipeline

```bash
# Обычная экстракция
curl -X POST http://localhost:8001/extract \
  -H "Content-Type: application/json" \
  -d '{"url":"https://www.youtube.com/watch?v=VIDEO_ID"}'

# → Worker автоматически:
# 1. Создаст embedding
# 2. Создаст структурированный конспект
```

### 2. Batch processing для старого контента

```python
# Python скрипт для обработки всех видео без embeddings
import requests

# Получить все ID без embeddings
content_ids = [20, 21, 22, ...]  # из БД

# Отправить задачи
for content_id in content_ids:
    requests.post(
        "http://localhost:8003/embed",
        json={"content_id": content_id}
    )
```

---

## 📊 Структурированный конспект

Новый формат summary (вместо простого краткого содержания):

```
🎯 ГЛАВНАЯ ТЕМА:
[Одно предложение]

📋 ОБЗОР:
[2-3 предложения контекста]

🔑 КЛЮЧЕВЫЕ ТЕМЫ:

1. [Тема 1]
   • Суть: определение
   • Важность: зачем это нужно
   • Детали: факты, цифры, примеры

2. [Тема 2]
   • Суть: ...
   • Важность: ...
   • Детали: ...

💡 ВЫВОДЫ:
1. [Вывод 1]
2. [Вывод 2]
3. [Вывод 3]

📊 ФАКТЫ/ЦИФРЫ:
• [Важная статистика 1]
• [Важная статистика 2]

🔗 СВЯЗАННЫЕ ТЕМЫ:
[Упомянутые темы]
```

**Преимущества:**
- ✅ Структурированная информация (не "простыня текста")
- ✅ Сохранены ВСЕ цифры и факты
- ✅ Иерархия: главное → детали
- ✅ Удобно сканировать глазами

---

## 🔧 Конфигурация

### Docker Compose

```yaml
# Worker service
worker:
  build: ./services/worker
  environment:
    REDIS_HOST: redis
    REDIS_PORT: 6379
    RAG_SERVICE_URL: http://rag_service:8000
    SUMMARIZER_URL: http://summarizer:8000
    WORKER_QUEUES: embedding,summarization,default

# Summarizer с увеличенным лимитом для конспектов
summarizer:
  environment:
    MAX_SUMMARY_LENGTH: 2000  # было 500
    TEMPERATURE: 0.3
```

### Переменные окружения

```bash
# Worker
REDIS_HOST=redis
REDIS_PORT=6379
WORKER_QUEUES=embedding,summarization,default

# Summarizer
MAX_SUMMARY_LENGTH=2000  # tokens для структурированных конспектов
TEMPERATURE=0.3  # lower = more focused
```

---

## 📈 Мониторинг

### Проверить очереди Redis

```bash
docker exec -it sambot_v2_redis redis-cli

# Посмотреть задачи
LLEN rq:queue:embedding
LLEN rq:queue:summarization

# Мониторинг worker
docker compose logs worker --tail 50 --follow
```

### Проверить результаты

```bash
# Проверить embedding
curl http://localhost:8003/search \
  -H "Content-Type: application/json" \
  -d '{"query":"Про что видео?", "min_similarity":0.3}'

# Проверить summary
curl http://localhost:8002/summary/20
```

---

## 🛠 Batch Processing Script

Создай файл `batch_embed.py`:

```python
#!/usr/bin/env python3
"""Batch embedding для всех видео без embeddings."""

import psycopg2
import requests
import time

# Подключение к БД
conn = psycopg2.connect(
    "postgresql://sambot:sambot_secure_pass_change_me@localhost:5432/sambot_v2"
)

# Найти контент без embeddings
cursor = conn.cursor()
cursor.execute("""
    SELECT id FROM original_content
    WHERE embedding IS NULL
    AND raw_content IS NOT NULL
""")

content_ids = [row[0] for row in cursor.fetchall()]
print(f"Found {len(content_ids)} videos without embeddings")

# Создать embeddings
for i, content_id in enumerate(content_ids, 1):
    print(f"[{i}/{len(content_ids)}] Processing content_id={content_id}")

    try:
        response = requests.post(
            "http://localhost:8003/embed",
            json={"content_id": content_id},
            timeout=120
        )

        if response.status_code == 200:
            print(f"✓ Success")
        else:
            print(f"✗ Failed: {response.text}")

        time.sleep(2)  # Rate limiting

    except Exception as e:
        print(f"✗ Error: {e}")

conn.close()
print("Done!")
```

Запуск:

```bash
python3 batch_embed.py
```

---

## 🎯 Что дальше?

- [ ] **Auto-trigger**: При экстракции автоматически запускать pipeline
- [ ] **Web UI**: Показывать прогресс обработки
- [ ] **Batch API**: `/batch/process` endpoint
- [ ] **Scheduled jobs**: Ночная обработка старого контента

---

## 🔍 Troubleshooting

### Worker не запускается

```bash
# Проверить Redis
docker compose logs redis

# Перезапустить worker
docker compose restart worker
```

### Embeddings не создаются

```bash
# Проверить Ollama
ollama list  # должен быть nomic-embed-text

# Проверить RAG service
curl http://localhost:8003/health
```

### Summary в старом формате

```bash
# Пересобрать summarizer
docker compose up -d summarizer --build

# Удалить старый summary
psql -d sambot_v2 -c "DELETE FROM summaries_cache WHERE content_id=20;"

# Создать новый
curl -X POST http://localhost:8002/summarize \
  -H "Content-Type: application/json" \
  -d '{"content_id":20}'
```

---

**Готово!** 🎉 Теперь вся обработка автоматическая.
