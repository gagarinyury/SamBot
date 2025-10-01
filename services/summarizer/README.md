# Summarizer Service

AI-powered content summarization using Ollama and Qwen 2.5.

## Features

- ✅ Summarizes YouTube/Instagram transcripts
- ✅ Uses local LLM (Qwen 2.5 3B)
- ✅ Supports Russian and English
- ✅ Caches summaries in PostgreSQL
- ✅ FastAPI REST API

## Architecture

```
summarizer (FastAPI) → ollama (Qwen 2.5 3B) → PostgreSQL
```

## Setup

### 1. Start services

```bash
# Build and start all services
docker compose up -d ollama summarizer

# Check logs
docker compose logs -f ollama summarizer
```

### 2. Download model

```bash
# Pull Qwen 2.5 3B model (first time only)
docker exec -it sambot_v2_ollama ollama pull qwen2.5:3b-instruct-q4_K_M

# Verify model
docker exec -it sambot_v2_ollama ollama list
```

## API Endpoints

### Health Check
```bash
curl http://localhost:8002/health
```

### Summarize Content
```bash
curl -X POST http://localhost:8002/summarize \
  -H "Content-Type: application/json" \
  -d '{"content_id": 1}'
```

### Get Existing Summary
```bash
curl http://localhost:8002/summary/1
```

## Configuration

Environment variables (in `docker-compose.yml`):

- `OLLAMA_URL` - Ollama API URL (default: `http://ollama:11434`)
- `MODEL_NAME` - LLM model (default: `qwen2.5:3b-instruct-q4_K_M`)
- `MAX_SUMMARY_LENGTH` - Max tokens (default: `500`)
- `TEMPERATURE` - Sampling temperature (default: `0.3`)

## Model Options

### Qwen 2.5 3B (Recommended)
```bash
ollama pull qwen2.5:3b-instruct-q4_K_M
```
- Fast (~5-10 sec per summary)
- Good for Russian + English
- Low RAM usage (3-4GB)

### Mistral 7B (More detailed)
```bash
ollama pull mistral:7b-instruct-q4_K_M
```
- Slower (~15-20 sec)
- More detailed summaries
- Higher RAM (6-8GB)

## Testing

```bash
# 1. Extract content first
curl -X POST http://localhost:8001/extract \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}'

# Response: {"content_id": 1, ...}

# 2. Summarize
curl -X POST http://localhost:8002/summarize \
  -H "Content-Type: application/json" \
  -d '{"content_id": 1}'
```

## Troubleshooting

### Ollama not responding
```bash
# Check Ollama logs
docker compose logs ollama

# Restart Ollama
docker compose restart ollama
```

### Model not found
```bash
# Pull model manually
docker exec -it sambot_v2_ollama ollama pull qwen2.5:3b-instruct-q4_K_M
```

### Out of memory
Use smaller model or reduce context:
```yaml
MODEL_NAME: qwen2.5:1.5b-instruct-q4_K_M
```
