"""Content extraction logic using yt-dlp."""

import os
import time
import yt_dlp
import tiktoken
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
import structlog

from config import settings
from database import db

logger = structlog.get_logger()


class ContentExtractor:
    """Universal content extractor using yt-dlp."""

    def __init__(self):
        self.audio_storage = Path(settings.AUDIO_STORAGE_PATH)
        self.audio_storage.mkdir(exist_ok=True, parents=True)
        self.tokenizer = tiktoken.get_encoding("cl100k_base")
        self._whisper_model = None  # Lazy load

    async def extract(
        self,
        url: str,
        user_id: Optional[int] = None,
        language: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Extract content from URL with automatic strategy detection.

        Strategy:
        1. Check cache (by url_hash)
        2. Extract metadata
        3. Try transcript (YouTube only)
        4. Fallback to audio download if no transcript

        Returns:
            Extraction result with content_id and metadata
        """
        start_time = time.time()

        # Step 1: Check cache
        cached = await db.check_cache(url)
        if cached:
            # Backward compatibility: add platform if missing (old records)
            metadata = cached['metadata']
            if 'platform' not in metadata:
                metadata['platform'] = cached['content_type']

            return {
                "status": "cached",
                "content_id": cached['id'],
                "strategy": "transcript" if cached['raw_content'] else "audio",
                "extraction_method": cached['extraction_method'],
                "metadata": metadata,
                "has_transcript": bool(cached['raw_content']),
                "has_audio": bool(cached['audio_file_path']),
                "transcript_length": len(cached['raw_content']) if cached['raw_content'] else None,
                "audio_file": cached['audio_file_path'],
                "total_chunks": cached['chunk_count'],
                "processing_time": 0.0
            }

        logger.info("extraction_started", url=url[:50])

        # Step 2: Extract metadata
        metadata = await self._extract_metadata(url)
        if not metadata:
            raise ValueError("Failed to extract metadata")

        platform = metadata['platform'].lower()
        is_youtube = 'youtube' in platform

        # Step 3: Try transcript (YouTube only)
        transcript = None
        audio_file = None
        strategy = "audio"
        extraction_method = "yt-dlp_audio"

        if is_youtube:
            transcript = await self._extract_transcript(url, language)

            if transcript:
                strategy = "transcript"
                extraction_method = "yt-dlp_transcript"
                logger.info("transcript_extracted", length=len(transcript))

        # Step 4: Download audio if no transcript
        if not transcript:
            audio_file = await self._download_audio(url)
            logger.info("audio_downloaded", file=audio_file)

            # Step 4.5: Transcribe audio with Whisper
            audio_path = self.audio_storage / audio_file
            transcript = await self._transcribe_audio(audio_path)
            if transcript:
                strategy = "whisper"
                extraction_method = "whisper_transcription"
                logger.info("whisper_transcription_completed", length=len(transcript))

        # Step 5: Save to database
        content_id = await db.save_content(
            url=url,
            content_type=platform,
            metadata=metadata,
            raw_content=transcript,
            audio_file_path=audio_file,
            extraction_method=extraction_method,
            user_id=user_id
        )

        # Step 6: Create chunks (only if transcript available)
        total_chunks = 0
        if transcript:
            chunks = self._create_chunks(transcript)
            total_chunks = await db.save_chunks(content_id, chunks)

        processing_time = time.time() - start_time

        logger.info(
            "extraction_completed",
            content_id=content_id,
            strategy=strategy,
            processing_time=f"{processing_time:.2f}s"
        )

        return {
            "status": "success",
            "content_id": content_id,
            "strategy": strategy,
            "extraction_method": extraction_method,
            "metadata": metadata,
            "has_transcript": bool(transcript),
            "has_audio": bool(audio_file),
            "transcript_length": len(transcript) if transcript else None,
            "audio_file": audio_file,
            "total_chunks": total_chunks,
            "processing_time": processing_time
        }

    def _extract_chapters_from_description(self, description: str) -> list:
        """
        Extract chapters from YouTube video description.
        Format: 00:00 — Chapter title or 0:34 — Chapter title
        """
        import re

        if not description:
            return []

        chapters = []
        # Match patterns like: 00:00, 0:34, 12:45, etc.
        pattern = r'(\d{1,2}:\d{2}(?::\d{2})?)\s*[-—–]\s*(.+?)(?:\n|$)'

        for match in re.finditer(pattern, description, re.MULTILINE):
            timestamp = match.group(1).strip()
            title = match.group(2).strip()

            # Convert timestamp to seconds
            parts = timestamp.split(':')
            if len(parts) == 2:  # MM:SS
                seconds = int(parts[0]) * 60 + int(parts[1])
            elif len(parts) == 3:  # HH:MM:SS
                seconds = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            else:
                continue

            chapters.append({
                'timestamp': timestamp,
                'seconds': seconds,
                'title': title
            })

        return chapters

    async def _extract_metadata_from_youtube_api(self, video_id: str) -> Optional[Dict[str, Any]]:
        """Extract YouTube metadata using YouTube Data API v3."""
        import aiohttp
        import re

        if not hasattr(settings, 'YOUTUBE_API_KEY') or not settings.YOUTUBE_API_KEY:
            return None

        try:
            api_url = f"https://www.googleapis.com/youtube/v3/videos?part=snippet,contentDetails&id={video_id}&key={settings.YOUTUBE_API_KEY}"

            async with aiohttp.ClientSession() as session:
                async with session.get(api_url) as resp:
                    if resp.status != 200:
                        logger.error("youtube_api_failed", status=resp.status)
                        return None

                    data = await resp.json()

                    if not data.get('items'):
                        logger.error("youtube_api_no_items")
                        return None

                    item = data['items'][0]
                    snippet = item['snippet']
                    content_details = item['contentDetails']

                    # Parse ISO 8601 duration (PT12M31S -> 751 seconds)
                    duration_str = content_details['duration']
                    duration_match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration_str)
                    hours = int(duration_match.group(1) or 0)
                    minutes = int(duration_match.group(2) or 0)
                    seconds = int(duration_match.group(3) or 0)
                    duration = hours * 3600 + minutes * 60 + seconds

                    # Extract chapters from description
                    chapters = self._extract_chapters_from_description(snippet.get('description', ''))

                    logger.info("youtube_api_success", title=snippet['title'][:50], chapters_found=len(chapters))

                    return {
                        'title': snippet['title'],
                        'channel': snippet['channelTitle'],
                        'duration': float(duration),
                        'description': snippet.get('description'),
                        'chapters': chapters,
                        'language': snippet.get('defaultAudioLanguage') or snippet.get('defaultLanguage'),
                        'platform': 'youtube',
                    }

        except Exception as e:
            logger.error("youtube_api_error", error=str(e))
            return None

    async def _extract_metadata(self, url: str) -> Optional[Dict[str, Any]]:
        """Extract metadata from URL."""

        # Try YouTube Data API v3 first for YouTube videos
        if 'youtube.com' in url or 'youtu.be' in url:
            import re
            video_id_match = re.search(r'(?:v=|/)([a-zA-Z0-9_-]{11})', url)
            if video_id_match:
                video_id = video_id_match.group(1)
                logger.info("trying_youtube_api", video_id=video_id)
                youtube_metadata = await self._extract_metadata_from_youtube_api(video_id)
                if youtube_metadata:
                    logger.info("youtube_api_metadata_success")
                    return youtube_metadata
                logger.info("youtube_api_failed_fallback_to_ytdlp")

        # Fallback to yt-dlp for all platforms
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
            'socket_timeout': settings.SOCKET_TIMEOUT,
        }

        # Add cookies if available (for Instagram, etc.)
        if hasattr(settings, 'COOKIES_FILE') and settings.COOKIES_FILE:
            if os.path.exists(settings.COOKIES_FILE):
                ydl_opts['cookiefile'] = settings.COOKIES_FILE

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

                if not info:
                    return None

                return {
                    'title': info.get('title', 'Unknown'),
                    'channel': info.get('uploader') or info.get('channel'),
                    'duration': info.get('duration'),
                    'description': info.get('description'),
                    'language': info.get('language'),
                    'platform': info.get('extractor', 'unknown')
                }

        except Exception as e:
            logger.error("metadata_extraction_failed", error=str(e))
            raise

    async def _extract_transcript(
        self,
        url: str,
        preferred_language: Optional[str] = None
    ) -> Optional[str]:
        """
        Extract transcript from YouTube video.

        DISABLED: YouTube subtitle extraction to avoid 429 bans.
        Use Whisper transcription instead.

        Returns:
            None (always use Whisper fallback)
        """
        logger.info("transcript_extraction_disabled_using_whisper_only")
        return None

        # COMMENTED OUT: YouTube subtitle extraction (causes 429 bans)
        # ydl_opts = {
        #     'quiet': True,
        #     'no_warnings': True,
        #     'skip_download': True,
        #     'writesubtitles': True,
        #     'writeautomaticsub': True,
        #     'subtitlesformat': 'json3',
        #     'socket_timeout': settings.SOCKET_TIMEOUT,
        # }
        #
        # try:
        #     with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        #         logger.info("yt_dlp_extracting_info")
        #         info = ydl.extract_info(url, download=False)
        #
        #         has_subs = bool(info.get('subtitles'))
        #         has_auto = bool(info.get('automatic_captions'))
        #
        #         logger.info("subtitle_check", has_manual=has_subs, has_auto=has_auto)
        #
        #         if not (has_subs or has_auto):
        #             logger.info("no_subtitles_found")
        #             return None
        #
        #         # Get subtitles source
        #         source = info.get('subtitles') or info.get('automatic_captions')
        #         available_langs = list(source.keys())
        #         logger.info("available_languages", langs=available_langs[:5])
        #
        #         # Find best language
        #         lang = self._find_best_language(
        #             source,
        #             preferred_language or info.get('language')
        #         )
        #
        #         if not lang:
        #             logger.error("no_suitable_language_found", available=available_langs[:5])
        #             return None
        #
        #         logger.info("selected_language", lang=lang)
        #
        #         # Get transcript URL - ONLY json3 format to avoid 429 bans
        #         json3_subtitle = None
        #         for sub in source[lang]:
        #             if sub.get('ext') == 'json3':
        #                 json3_subtitle = sub
        #                 break
        #
        #         if not json3_subtitle:
        #             logger.error("no_json3_subtitle_found", available=[s.get('ext') for s in source[lang]])
        #             return None
        #
        #         sub_url = json3_subtitle.get('url')
        #         if not sub_url:
        #             logger.error("no_subtitle_url_found")
        #             return None
        #
        #         logger.info("downloading_transcript", format="json3", url=sub_url[:70])
        #         # Download and parse transcript
        #         transcript = await self._download_transcript(sub_url)
        #
        #         if transcript:
        #             logger.info("transcript_extracted", length=len(transcript))
        #             return transcript
        #         else:
        #             logger.error("transcript_download_returned_empty")
        #             return None
        #
        # except Exception as e:
        #     logger.error("transcript_extraction_failed", error=str(e))
        #     return None

    def _find_best_language(
        self,
        subtitles: Dict[str, Any],
        preferred: Optional[str]
    ) -> Optional[str]:
        """Find best available subtitle language."""
        available = list(subtitles.keys())

        if not available:
            return None

        # Try preferred language
        if preferred and preferred in available:
            return preferred

        # Try common languages
        for lang in ['ru', 'en', 'en-US', 'en-GB']:
            if lang in available:
                return lang

        # Return first available
        return available[0]

    async def _download_transcript(self, url: str) -> str:
        """Download and parse transcript from URL using aiohttp."""
        import aiohttp
        import json
        import re

        try:
            # Use aiohttp instead of requests (works better in Docker)
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    logger.info("transcript_response", status=resp.status, content_type=resp.headers.get('Content-Type'))

                    if resp.status != 200:
                        logger.error("transcript_download_failed", status=resp.status, url=url[:50])
                        return ""

                    content = await resp.text()
                    logger.info("transcript_content_received", length=len(content))

                    if not content:
                        logger.error("transcript_download_empty", url=url[:50])
                        return ""

                    # Parse based on format
                    if 'json' in url:
                        # JSON3 format from YouTube
                        data = json.loads(content)
                        texts = []
                        for event in data.get('events', []):
                            if 'segs' in event:
                                for seg in event['segs']:
                                    if 'utf8' in seg:
                                        texts.append(seg['utf8'])
                        return ' '.join(texts)
                    else:
                        # VTT or SRT format
                        text = content
                        # Remove timestamps and formatting
                        text = re.sub(r'\d{2}:\d{2}:\d{2}[.,]\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}[.,]\d{3}', '', text)
                        text = re.sub(r'^\d+\s*$', '', text, flags=re.MULTILINE)
                        text = re.sub(r'<[^>]+>', '', text)  # Remove tags
                        text = re.sub(r'\n+', ' ', text)
                        return text.strip()

        except Exception as e:
            logger.error("transcript_download_failed", error=str(e))
            return ""

    async def _download_audio(self, url: str) -> str:
        """
        Download audio from URL.

        Returns:
            Filename (not full path) of downloaded audio
        """
        # Generate unique filename
        import hashlib
        url_hash = hashlib.sha256(url.encode()).hexdigest()[:12]
        filename = f"{url_hash}.mp3"
        output_path = self.audio_storage / filename

        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': str(output_path.with_suffix('')),  # without extension
            'quiet': True,
            'no_warnings': True,
            'socket_timeout': settings.SOCKET_TIMEOUT,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': settings.PREFERRED_AUDIO_FORMAT,
                'preferredquality': str(settings.MAX_AUDIO_QUALITY),
            }],
        }

        # Add cookies if available
        if hasattr(settings, 'COOKIES_FILE') and settings.COOKIES_FILE:
            if os.path.exists(settings.COOKIES_FILE):
                ydl_opts['cookiefile'] = settings.COOKIES_FILE

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            # Return just filename (not full path)
            return filename

        except Exception as e:
            logger.error("audio_download_failed", error=str(e))
            raise

    async def _transcribe_audio(self, audio_path: Path) -> Optional[str]:
        """
        Transcribe audio file using faster-whisper (4x speed improvement).

        Args:
            audio_path: Path to audio file

        Returns:
            Transcribed text or None if failed
        """
        try:
            from faster_whisper import WhisperModel

            # Lazy load model (heavy operation)
            if self._whisper_model is None:
                logger.info("loading_faster_whisper_model", model=settings.WHISPER_MODEL)
                self._whisper_model = WhisperModel(
                    settings.WHISPER_MODEL,
                    device=settings.WHISPER_DEVICE,
                    compute_type="int8"  # Faster on CPU
                )
                logger.info("faster_whisper_model_loaded")

            logger.info("transcribing_audio_faster_whisper", file=audio_path.name)

            # Transcribe (4x faster than vanilla Whisper!)
            segments, info = self._whisper_model.transcribe(
                str(audio_path),
                language=settings.WHISPER_LANGUAGE,
                beam_size=5  # Good balance between speed and accuracy
            )

            # Extract text from segments
            transcript = " ".join([seg.text for seg in segments]).strip()

            logger.info(
                "faster_whisper_transcription_completed",
                detected_language=info.language,
                length=len(transcript)
            )

            return transcript if transcript else None

        except Exception as e:
            logger.error("faster_whisper_transcription_failed", error=str(e))
            return None

    def _create_chunks(self, text: str) -> List[Dict[str, Any]]:
        """
        Split text into chunks for RAG.

        Returns:
            List of chunks with metadata
        """
        tokens = self.tokenizer.encode(text)
        chunks = []

        chunk_size = settings.DEFAULT_CHUNK_SIZE
        overlap = settings.DEFAULT_CHUNK_OVERLAP

        for i in range(0, len(tokens), chunk_size - overlap):
            chunk_tokens = tokens[i:i + chunk_size]
            chunk_text = self.tokenizer.decode(chunk_tokens)

            chunks.append({
                'text': chunk_text,
                'index': len(chunks),
                'tokens': len(chunk_tokens),
                'start_timestamp': None,  # TODO: Extract from transcript
                'end_timestamp': None
            })

        return chunks


# Global extractor instance
extractor = ContentExtractor()