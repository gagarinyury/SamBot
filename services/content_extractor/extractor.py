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

    async def _extract_metadata(self, url: str) -> Optional[Dict[str, Any]]:
        """Extract metadata from URL."""
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

        Returns:
            Full transcript text or None if not available
        """
        logger.info("transcript_extraction_start", url=url[:50])

        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
            'writesubtitles': True,
            'writeautomaticsub': True,
            'socket_timeout': settings.SOCKET_TIMEOUT,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                logger.info("yt_dlp_extracting_info")
                info = ydl.extract_info(url, download=False)

                has_subs = bool(info.get('subtitles'))
                has_auto = bool(info.get('automatic_captions'))

                logger.info("subtitle_check", has_manual=has_subs, has_auto=has_auto)

                if not (has_subs or has_auto):
                    logger.info("no_subtitles_found")
                    return None

                # Get subtitles source
                source = info.get('subtitles') or info.get('automatic_captions')
                available_langs = list(source.keys())
                logger.info("available_languages", langs=available_langs[:5])

                # Find best language
                lang = self._find_best_language(
                    source,
                    preferred_language or info.get('language')
                )

                if not lang:
                    logger.error("no_suitable_language_found", available=available_langs[:5])
                    return None

                logger.info("selected_language", lang=lang)

                # Get transcript URL
                for sub in source[lang]:
                    sub_url = sub.get('url')
                    sub_ext = sub.get('ext')
                    logger.info("checking_subtitle", ext=sub_ext, has_url=bool(sub_url))

                    if sub_url:
                        logger.info("downloading_transcript", url=sub_url[:70])
                        # Download and parse transcript
                        transcript = await self._download_transcript(sub_url)

                        if transcript:
                            logger.info("transcript_extracted", length=len(transcript))
                            return transcript
                        else:
                            logger.error("transcript_download_returned_empty")

                logger.error("no_subtitle_url_found")
                return None

        except Exception as e:
            logger.error("transcript_extraction_failed", error=str(e))
            return None

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