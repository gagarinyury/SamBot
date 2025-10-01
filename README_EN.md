# 🎥 SamBot v2 - AI-Powered YouTube Content Processor

> **Turn YouTube videos into structured notes with AI**

Stop wasting hours watching long videos. SamBot extracts transcripts, creates detailed summaries with AI, and lets you ask questions through semantic search.

**🚀 Fast.** Subtitles extracted in seconds. AI summaries stream in real-time.

**💰 Cheap.** DeepSeek API costs pennies (~$0.0003 per video). Or use free local Ollama.

**🎯 Quality.** Structured summaries with emoji, markdown, and key insights. RAG system for accurate answers.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-required-blue.svg)](https://www.docker.com/)

## ⭐ Star us on GitHub — it motivates us to keep improving!

## 🎯 Features (Actually Working)

- ✅ **Content Extraction** from YouTube videos (subtitles + Whisper for audio)
- ✅ **AI Summarization** via DeepSeek API or local Ollama
- ✅ **RAG (Retrieval-Augmented Generation)** - semantic search and Q&A over video content
- ✅ **Streaming UI** - real-time progress display for extraction and summaries
- ✅ **Background Processing** - automatic embeddings creation
- ✅ **PostgreSQL + pgvector** - store transcripts and vectors

## 🚧 In Development

- 🔄 **Telegram Bot** - will be added as primary interface
- 🔄 **Web UI Improvements** - current UI is basic, planning enhancements

## 🏗 Architecture

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

## 🛠 Tech Stack

**Backend:**
- Python 3.11 + FastAPI
- PostgreSQL 16 + pgvector (vector database)
- Redis + RQ (background tasks)

**AI:**
- DeepSeek API (236B model, streaming)
- Ollama (local alternative, qwen2.5:7b/14b/32b)
- nomic-embed-text (embeddings)

**Extraction:**
- yt-dlp (YouTube subtitles)
- faster-whisper (audio transcription)
- YouTube Data API v3 (metadata)

## 🚀 Quick Start

### Requirements

- Docker + Docker Compose
- 8+ GB RAM
- DeepSeek API key or Ollama

### 1. Clone

```bash
git clone https://github.com/gagarinyury/SamBot.git
cd SamBot
```

### 2. Configure

```bash
# Copy config template
cp .env.example .env

# Edit .env
nano .env
```

Minimal `.env` configuration:

```bash
# Database
DB_PASSWORD=your_secure_password

# YouTube API (optional, for metadata)
YOUTUBE_API_KEY=your_youtube_api_key

# AI Provider: deepseek or ollama
AI_PROVIDER=deepseek

# DeepSeek API (if AI_PROVIDER=deepseek)
DEEPSEEK_API_KEY=sk-your-deepseek-key

# Ollama model (if AI_PROVIDER=ollama)
SUMMARIZER_MODEL=qwen2.5:7b-instruct-q4_K_M
```

### 3. For Ollama (if not using DeepSeek)

```bash
# Install Ollama
brew install ollama  # macOS
# or download from https://ollama.com

# Start Ollama
ollama serve

# Pull models
ollama pull qwen2.5:7b-instruct-q4_K_M  # 5GB RAM
ollama pull nomic-embed-text            # embeddings
```

### 4. Launch

```bash
# Start all services
docker compose up -d

# Check status
docker compose ps

# View logs
docker compose logs -f
```

### 5. Use

Open Web UI: http://localhost:8080

1. Paste YouTube URL
2. Click "Extract Content"
3. Wait for extraction (1-2 min for audio, 5-10 sec for subtitles)
4. Click "Create Summary" for AI summary
5. Ask questions in RAG Q&A section

## 🎨 Capabilities

### 1. Content Extraction

**Extraction strategies:**
1. YouTube subtitles (fast, ~5 sec)
2. Whisper transcription (slower, 1-2 min, high quality)

**What's extracted:**
- Transcript (clean text, no WEBVTT garbage)
- Metadata (title, channel, duration, description)
- Video chapters (if present in description)

### 2. AI Summarization

**Two modes:**

**A) DeepSeek API (recommended):**
- ✅ Fast (~2-5 sec start, streaming)
- ✅ Top quality (236B parameters)
- ✅ Cheap (~$0.0001-0.0003 per video)
- ✅ Structured format (emoji, markdown)

**B) Ollama (local):**
- ✅ Free
- ✅ Privacy
- ⚠️ Slower (30-60 sec for 7B model)
- ⚠️ Requires RAM (5GB for 7B, 9GB for 14B, 20GB for 32B)

**Summary format:**
```markdown
## 🎯 MAIN TOPIC
[One sentence]

## 📋 OVERVIEW
[2-3 sentences]

## 🔑 KEY SECTIONS
### 1. [Section name]
- **Key point**: ...
- **Details**: ...
- **Why important**: ...

## 💡 KEY TAKEAWAYS
1. ...
2. ...

## 📊 FACTS & FIGURES
- ...
```

### 3. RAG (Semantic Search + Q&A)

**How it works:**
1. Transcript splits into chunks (~500 tokens)
2. Each chunk gets an embedding (768-dim vector)
3. When you ask - similarity search via pgvector
4. LLM generates answer based on retrieved context

**Parameters:**
- `SIMILARITY_THRESHOLD`: 0.5 (cosine similarity)
- `TOP_K_RESULTS`: 3 (chunks for context)
- `content_id` filter: search only in specific video

## 📈 Performance

**Typical processing time:**

| Operation | Time | Note |
|----------|------|------|
| Extraction (subtitles) | 5-10 sec | Fast |
| Extraction (Whisper) | 1-2 min | Depends on video length |
| Embeddings creation | 10-30 sec | Background, automatic |
| Summary (DeepSeek) | 5-15 sec | Streaming, see progress |
| Summary (Ollama 7B) | 30-60 sec | Local, slower |
| RAG Q&A | 2-5 sec | Fast search + LLM |

**Cost (DeepSeek):**
- Summary: ~$0.0001-0.0003 per video
- RAG Q&A: ~$0.00005 per question
- 1000 videos ≈ $0.20-0.30

## ⚙️ Configuration

### Switch AI Provider

```bash
# To DeepSeek
echo "AI_PROVIDER=deepseek" >> .env
docker compose restart summarizer rag_service

# To Ollama
echo "AI_PROVIDER=ollama" >> .env
docker compose restart summarizer rag_service
```

### Choose Ollama Model

```bash
# Download model
ollama pull qwen2.5:14b  # 9GB RAM, better quality

# Update config
echo "SUMMARIZER_MODEL=qwen2.5:14b" >> .env
docker compose restart summarizer
```

**Available models:**
- `qwen2.5:3b` (~2GB RAM, basic quality)
- `qwen2.5:7b` (~5GB RAM, good quality) ⭐ recommended
- `qwen2.5:14b` (~9GB RAM, excellent quality)
- `qwen2.5:32b` (~20GB RAM, maximum quality)

## 🐛 Troubleshooting

### Extraction not working

```bash
# Check logs
docker compose logs content_extractor

# Common causes:
# - YouTube blocked IP → add cookies.txt
# - No subtitles → will use Whisper (slow)
# - YouTube API key missing → metadata via yt-dlp
```

### Summary not generating

```bash
# Check AI provider
docker compose logs summarizer

# DeepSeek:
# - Check API key in .env
# - Check limits at platform.deepseek.com

# Ollama:
# - Check Ollama is running: ollama list
# - Check model is downloaded
```

### RAG returns no results

```bash
# Check embeddings
docker compose exec postgres psql -U sambot -d sambot_v2 \
  -c "SELECT COUNT(*) FROM content_embeddings;"

# If embeddings = 0:
# - Worker didn't create embeddings
# - Check: docker compose logs worker
```

## 📁 Project Structure

```
sambot-v2/
├── docker-compose.yml              # Service orchestration
├── .env                            # Configuration (not in git)
├── .env.example                    # Config template
├── README.md                       # This documentation
│
├── migrations/                     # SQL migrations
│   ├── 01_init_schema.sql         # Core tables
│   └── 02_rag_tables.sql          # RAG tables
│
├── services/
│   ├── content_extractor/         # YouTube extraction
│   ├── summarizer/                # AI summarization
│   ├── rag_service/               # Semantic search + Q&A
│   ├── web_ui/                    # Web interface
│   └── worker/                    # Background tasks
│
└── ... (see full docs)
```

## 🚀 Roadmap

**Planned:**
1. **Telegram Bot** - primary interface
2. **Improved Web UI** - better UX/UI
3. **Batch processing** - multiple videos
4. **Export** - Notion, Obsidian, Markdown
5. **Multi-language** - UI in Russian/English

## 🤝 Contributing

Project is actively developed. Pull requests are welcome!

### How to contribute:
1. ⭐ Star the repo
2. 🍴 Fork it
3. 🔨 Create your feature branch
4. 📝 Commit your changes
5. 🚀 Push and create a Pull Request

## 📚 Links

- [DeepSeek Platform](https://platform.deepseek.com)
- [Ollama](https://ollama.com)
- [pgvector](https://github.com/pgvector/pgvector)
- [FastAPI](https://fastapi.tiangolo.com)
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)

## 📄 License

MIT License - feel free to use in your projects!

---

**⭐ If you like this project, please star it on GitHub!**

**Status:** ✅ Working (core features)
**Last updated:** October 1, 2025

---

Made with ❤️ by developers who hate watching hour-long videos
