"""Simple Flask web UI for SamBot content extraction."""

import os
import requests
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

EXTRACTOR_URL = os.getenv('EXTRACTOR_URL', 'http://content_extractor:8000')
SUMMARIZER_URL = os.getenv('SUMMARIZER_URL', 'http://summarizer:8000')


@app.route('/')
def index():
    """Main page with URL input form."""
    return render_template('index.html')


@app.route('/extract', methods=['POST'])
def extract():
    """Extract content from URL."""
    data = request.get_json()
    url = data.get('url')

    if not url:
        return jsonify({'error': 'URL is required'}), 400

    try:
        # Call content extractor API (increased timeout for long videos)
        response = requests.post(
            f'{EXTRACTOR_URL}/extract',
            json={'url': url},
            timeout=300  # 5 minutes for Whisper on long videos
        )

        if response.status_code != 200:
            return jsonify({'error': response.text}), response.status_code

        result = response.json()
        content_id = result.get('content_id')

        # Get full content with chunks
        content_response = requests.get(
            f'{EXTRACTOR_URL}/content/{content_id}',
            timeout=30
        )

        if content_response.status_code != 200:
            return jsonify(result), 200

        full_content = content_response.json()

        # Combine results
        result['full_transcript'] = ''
        if full_content.get('chunks'):
            import json
            chunks = json.loads(full_content['chunks']) if isinstance(full_content['chunks'], str) else full_content['chunks']
            result['full_transcript'] = ' '.join([c['text'] for c in chunks])

        return jsonify(result), 200

    except requests.exceptions.Timeout:
        return jsonify({'error': 'Request timeout'}), 504
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/summarize/<int:content_id>', methods=['POST'])
def summarize(content_id):
    """Generate summary for extracted content."""
    try:
        # Call summarizer API
        response = requests.post(
            f'{SUMMARIZER_URL}/summarize',
            json={'content_id': content_id},
            timeout=180  # 3 minutes for LLM generation
        )

        if response.status_code != 200:
            return jsonify({'error': response.text}), response.status_code

        return jsonify(response.json()), 200

    except requests.exceptions.Timeout:
        return jsonify({'error': 'Summarization timeout'}), 504
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/summary/<int:content_id>', methods=['GET'])
def get_summary(content_id):
    """Get existing summary for content."""
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


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
