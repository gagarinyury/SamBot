"""Modern streaming Web UI for SamBot with real-time logs and streaming summarization."""

import os
import json
import time
import re
import requests
from flask import Flask, render_template, request, jsonify, Response, stream_with_context

app = Flask(__name__)

EXTRACTOR_URL = os.getenv('EXTRACTOR_URL', 'http://content_extractor:8000')
SUMMARIZER_URL = os.getenv('SUMMARIZER_URL', 'http://summarizer:8000')
RAG_URL = os.getenv('RAG_SERVICE_URL', 'http://rag_service:8000')
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY', '')


def extract_video_id(url: str) -> str:
    """Extract video ID from YouTube URL."""
    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/)([a-zA-Z0-9_-]{11})',
        r'youtube\.com\/embed\/([a-zA-Z0-9_-]{11})',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def get_youtube_metadata(video_id: str) -> dict:
    """Get YouTube metadata via API (fast, before Whisper)."""
    if not YOUTUBE_API_KEY:
        return {}

    try:
        api_url = f'https://www.googleapis.com/youtube/v3/videos'
        params = {
            'part': 'snippet,contentDetails',
            'id': video_id,
            'key': YOUTUBE_API_KEY
        }
        response = requests.get(api_url, params=params, timeout=5)

        if response.status_code != 200:
            return {}

        data = response.json()
        if not data.get('items'):
            return {}

        item = data['items'][0]
        snippet = item.get('snippet', {})
        content_details = item.get('contentDetails', {})

        # Parse ISO 8601 duration
        duration_str = content_details.get('duration', 'PT0S')
        duration_match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration_str)
        hours = int(duration_match.group(1) or 0)
        minutes = int(duration_match.group(2) or 0)
        seconds = int(duration_match.group(3) or 0)
        duration = hours * 3600 + minutes * 60 + seconds

        return {
            'title': snippet.get('title', 'N/A'),
            'duration': duration,
            'channel': snippet.get('channelTitle', 'N/A'),
            'published_at': snippet.get('publishedAt', 'N/A')
        }
    except Exception:
        return {}


@app.route('/')
def index():
    """Main page with Telegram Web App UI."""
    return render_template('index_telegram.html')


@app.route('/extract/stream', methods=['POST'])
def extract_stream():
    """Extract content with real-time progress streaming via SSE."""
    data = request.get_json()
    url = data.get('url')

    if not url:
        return jsonify({'error': 'URL is required'}), 400

    def generate():
        """Stream extraction progress events with detailed stages."""
        try:
            # Stage 1: Start
            yield f"data: {json.dumps({'status': 'started', 'message': '🚀 Запуск обработки...'})}\n\n"
            time.sleep(0.2)

            # Stage 2: Extract video ID and get metadata FIRST (fast!)
            video_id = extract_video_id(url)
            if not video_id:
                yield f"data: {json.dumps({'status': 'error', 'message': '❌ Некорректная ссылка YouTube'})}\n\n"
                return

            yield f"data: {json.dumps({'status': 'connecting', 'message': '🔗 Подключение к YouTube API...'})}\n\n"
            time.sleep(0.2)

            # Get metadata immediately
            metadata = get_youtube_metadata(video_id)
            if metadata:
                title = metadata.get('title', 'N/A')
                duration = metadata.get('duration', 0)
                duration_min = f"{int(duration / 60)} мин {duration % 60} сек" if duration else "N/A"
                channel = metadata.get('channel', 'N/A')

                yield f"data: {json.dumps({'status': 'metadata_received', 'message': '✅ Метаданные получены'})}\n\n"
                time.sleep(0.1)
                yield f"data: {json.dumps({'status': 'metadata_display', 'message': f'📺 {title[:60]}...' if len(title) > 60 else f'📺 {title}'})}\n\n"
                time.sleep(0.1)
                yield f"data: {json.dumps({'status': 'metadata_display', 'message': f'⏱️ Длительность: {duration_min}'})}\n\n"
                time.sleep(0.1)
                yield f"data: {json.dumps({'status': 'metadata_display', 'message': f'📢 Канал: {channel}'})}\n\n"
                time.sleep(0.2)

            # Stage 3: Start extraction (blocking call)
            yield f"data: {json.dumps({'status': 'downloading_audio', 'message': '🎵 Загрузка аудио...'})}\n\n"
            time.sleep(0.5)

            yield f"data: {json.dumps({'status': 'processing', 'message': '🎧 Обработка (Whisper AI работает, это займёт 1-2 мин)...'})}\n\n"
            time.sleep(0.5)

            # Call extractor API - this WILL block during Whisper transcription
            # Real streaming would require WebSocket or polling endpoint in extractor
            start_time = time.time()

            try:
                response = requests.post(
                    f'{EXTRACTOR_URL}/extract',
                    json={'url': url},
                    timeout=600
                )
            except requests.exceptions.RequestException as e:
                yield f"data: {json.dumps({'status': 'error', 'message': f'❌ Ошибка: {str(e)[:100]}'})}\n\n"
                return

            extraction_time = time.time() - start_time

            if response.status_code != 200:
                yield f"data: {json.dumps({'status': 'error', 'message': f'❌ Ошибка: {response.text[:200]}'})}\n\n"
                return

            result = response.json()
            content_id = result.get('content_id')

            yield f"data: {json.dumps({'status': 'whisper_done', 'message': f'✅ Транскрипция завершена за {int(extraction_time)}s'})}\n\n"
            time.sleep(0.3)

            # Stage 4: Extraction completed - get full content
            yield f"data: {json.dumps({'status': 'extraction_completed', 'message': '✅ Извлечение завершено', 'content_id': content_id})}\n\n"
            time.sleep(0.2)

            # Get full content
            content_response = requests.get(
                f'{EXTRACTOR_URL}/content/{content_id}',
                timeout=30
            )

            if content_response.status_code != 200:
                yield f"data: {json.dumps({'status': 'partial', 'message': '⚠️ Частичное извлечение', 'result': result})}\n\n"
                return

            full_content = content_response.json()
            final_metadata = full_content.get('metadata', {})

            # Parse metadata if it's a JSON string
            if isinstance(final_metadata, str):
                final_metadata = json.loads(final_metadata)

            # Stage 9: Create chunks
            yield f"data: {json.dumps({'status': 'creating_chunks', 'message': '📦 Разбиение на чанки для эмбедингов...'})}\n\n"
            time.sleep(0.3)

            # Extract transcript
            full_transcript = ''
            chunks_count = 0
            if full_content.get('chunks'):
                chunks = json.loads(full_content['chunks']) if isinstance(full_content['chunks'], str) else full_content['chunks']
                full_transcript = ' '.join([c['text'] for c in chunks])
                chunks_count = len(chunks)

            yield f"data: {json.dumps({'status': 'chunks_created', 'message': f'✅ Создано {chunks_count} чанков'})}\n\n"
            time.sleep(0.2)

            # Stage 5: Completion
            result['full_transcript'] = full_transcript
            result['metadata'] = final_metadata

            yield f"data: {json.dumps({'status': 'completed', 'message': f'🎉 Готово за {int(extraction_time)}s!', 'result': result})}\n\n"

        except requests.exceptions.Timeout:
            yield f"data: {json.dumps({'status': 'error', 'message': '⏱️ Request timeout - video too long'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'status': 'error', 'message': f'❌ Error: {str(e)}'})}\n\n"

    return Response(stream_with_context(generate()), mimetype='text/event-stream')


@app.route('/summarize/stream/<int:content_id>', methods=['POST'])
def summarize_stream(content_id):
    """Generate summary with real-time streaming via SSE (like ChatGPT)."""
    def generate():
        """Stream summary generation token by token."""
        try:
            yield f"data: {json.dumps({'status': 'started', 'message': '📝 Generating structured summary...'})}\n\n"
            time.sleep(0.1)

            # Call summarizer API with streaming
            response = requests.post(
                f'{SUMMARIZER_URL}/summarize',
                json={'content_id': content_id},
                timeout=300,  # 5 minutes
                stream=False  # For now, non-streaming (Ollama streaming requires different approach)
            )

            if response.status_code != 200:
                yield f"data: {json.dumps({'status': 'error', 'message': f'❌ Error: {response.text}'})}\n\n"
                return

            result = response.json()

            # Simulate streaming output (chunked display)
            summary_text = result.get('summary', '')

            # Split by lines for progressive display
            lines = summary_text.split('\n')
            accumulated = ''

            for line in lines:
                accumulated += line + '\n'
                yield f"data: {json.dumps({'status': 'generating', 'text': accumulated})}\n\n"
                time.sleep(0.05)  # Smooth display

            yield f"data: {json.dumps({'status': 'completed', 'summary': summary_text, 'result': result})}\n\n"

        except requests.exceptions.Timeout:
            yield f"data: {json.dumps({'status': 'error', 'message': '⏱️ Summarization timeout'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'status': 'error', 'message': f'❌ Error: {str(e)}'})}\n\n"

    return Response(stream_with_context(generate()), mimetype='text/event-stream')


@app.route('/rag/ask/stream', methods=['POST'])
def rag_ask_stream():
    """Ask question with RAG context, streaming response."""
    data = request.get_json()
    question = data.get('question')
    content_id = data.get('content_id')

    if not question:
        return jsonify({'error': 'Question is required'}), 400

    def generate():
        """Stream RAG answer."""
        try:
            yield f"data: {json.dumps({'status': 'started', 'message': '🔍 Searching relevant context...'})}\n\n"

            # Call RAG service
            response = requests.post(
                f'{RAG_URL}/ask',
                json={'question': question, 'content_id': content_id},
                timeout=180
            )

            if response.status_code != 200:
                yield f"data: {json.dumps({'status': 'error', 'message': f'❌ Error: {response.text}'})}\n\n"
                return

            result = response.json()
            answer = result.get('answer', '')

            # Stream answer progressively
            words = answer.split(' ')
            accumulated = ''

            for i, word in enumerate(words):
                accumulated += word + ' '
                if i % 3 == 0:  # Update every 3 words for smoothness
                    yield f"data: {json.dumps({'status': 'generating', 'text': accumulated})}\n\n"
                    time.sleep(0.02)

            yield f"data: {json.dumps({'status': 'completed', 'answer': answer, 'sources': result.get('sources', [])})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'status': 'error', 'message': f'❌ Error: {str(e)}'})}\n\n"

    return Response(stream_with_context(generate()), mimetype='text/event-stream')


@app.route('/summary/<int:content_id>', methods=['GET'])
def get_summary(content_id):
    """Get existing summary (non-streaming)."""
    try:
        response = requests.get(
            f'{SUMMARIZER_URL}/summary/{content_id}',
            timeout=30
        )

        if response.status_code == 404:
            return jsonify({'summary': None}), 200

        if response.status_code != 200:
            return jsonify({'error': response.text}), response.status_code

        return jsonify(response.json()), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/health')
def health():
    """Health check endpoint."""
    return jsonify({'status': 'healthy', 'service': 'web_ui_streaming'}), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
