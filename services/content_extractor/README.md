# Content Extractor Service

**Phase 1:** YouTube extraction with intelligent chapter-based chunking.

## Features

✅ **YouTube transcript extraction** (youtube-transcript-api)
✅ **Chapter detection** from video metadata
✅ **Intelligent chunking strategies**:
- Chapter-based (primary): splits by video chapters
- Fixed-size (fallback): splits by tokens with overlap
✅ **PostgreSQL storage** with chunks
✅ **FastAPI REST API**

## Project Structure

```
content_extractor/
├── main.py                    # FastAPI application
├── extractors/
│   ├── youtube.py            # YouTube extractor (from v1)
│   └── chapters.py           # Chapter detection (from v1)
├── chunking/
│   ├── chapter_based.py      # Chapter-based chunking
│   └── fixed_size.py         # Fixed-size chunking
├── database/
│   ├── connection.py         # PostgreSQL pool
│   └── repository.py         # Data access layer
├── Dockerfile
└── requirements.txt
```

## API Endpoints

### POST `/extract`

Extract content from YouTube URL.

**Request:**
```json
{
  "url": "https://youtube.com/watch?v=xxx",
  "user_id": 123,
  "language": "ru"
}
```

**Response:**
```json
{
  "status": "success",
  "content_id": 456,
  "platform": "youtube",
  "extraction_method": "youtube_transcript_api",
  "metadata": {
    "title": "Video Title",
    "duration": 2700,
    "chapters": {...}
  },
  "chunking": {
    "strategy": "chapter_based",
    "total_chunks": 5
  },
  "processing_time": 3.5
}
```

### GET `/content/{content_id}`

Get content and chunks by ID.

### GET `/health`

Health check.

## Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variable
export DATABASE_URL="postgresql://sambot:password@localhost:5432/sambot_v2"

# Run service
python main.py
```

## Docker Build & Run

```bash
# From sambot-v2 root directory
cd services/content_extractor

# Build
docker build -t content_extractor:latest .

# Run standalone
docker run -p 8001:8000 \
  -e DATABASE_URL="postgresql://sambot:password@host.docker.internal:5432/sambot_v2" \
  content_extractor:latest
```

## Docker Compose Integration

Service is already configured in `../../docker-compose.yml`:

```bash
# From sambot-v2 root
docker-compose up content_extractor
```

## Testing

```bash
# Health check
curl http://localhost:8001/health

# Extract YouTube video
curl -X POST http://localhost:8001/extract \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://youtube.com/watch?v=dQw4w9WgXcQ",
    "language": "en"
  }'

# Get content
curl http://localhost:8001/content/1
```

## Chunking Logic

### Chapter-Based (Priority)

**Activates when:**
- Video has chapters in description
- At least 2 chapters
- Video duration > 10 minutes
- Chapters cover >50% of video

**Benefits:**
- Semantic boundaries (natural chapters)
- Better for long videos
- Preserves context

### Fixed-Size (Fallback)

**Activates when:**
- No chapters detected
- Chapters unsuitable

**Parameters:**
- Short videos (<30 min): 1 chunk
- Medium (30-120 min): 500 tokens, 50 overlap
- Long (120+ min): 1000 tokens, 100 overlap

## Database Schema

Content stored in:
- `original_content` - full transcript + metadata
- `content_chunks` - chunks with timestamps
- `chunking_strategies` - strategy used

## Next Steps (Phase 2)

- [ ] Whisper integration for audio transcription
- [ ] yt-dlp multi-platform support (TikTok, Instagram, VK)
- [ ] Audio file storage
- [ ] Background task queue (Redis)