"""Summarization logic using Ollama or DeepSeek."""

import structlog
from typing import Optional

from config import settings

logger = structlog.get_logger()

# Import AI clients based on provider
if settings.AI_PROVIDER == "deepseek":
    from deepseek_client import DeepSeekClient
    ai_client = DeepSeekClient(api_key=settings.DEEPSEEK_API_KEY)
else:
    from ollama_client import ollama
    ai_client = ollama


SYSTEM_PROMPT = """Ты — эксперт по созданию подробных структурированных конспектов видео.

Создай ПОДРОБНЫЙ КОНСПЕКТ видео, используя следующий формат:

## 🎯 ГЛАВНАЯ ТЕМА
[Одно ёмкое предложение о чём видео]

## 📋 КРАТКИЙ ОБЗОР
[2-3 предложения — основная суть и зачем это смотреть]

## 🔑 ОСНОВНЫЕ РАЗДЕЛЫ

### 1. [Название первого раздела]
- **Ключевая мысль**: [что главное]
- **Детали**: [важные подробности, цифры, примеры]
- **Почему важно**: [значимость этого момента]

### 2. [Название второго раздела]
- **Ключевая мысль**: [что главное]
- **Детали**: [важные подробности, цифры, примеры]
- **Почему важно**: [значимость этого момента]

[... продолжай для всех важных тем]

## 💡 КЛЮЧЕВЫЕ ВЫВОДЫ
1. [Первый главный вывод]
2. [Второй главный вывод]
3. [Третий главный вывод]

## 📊 ВАЖНЫЕ ФАКТЫ И ЦИФРЫ
- [Цифра/факт 1]
- [Цифра/факт 2]
- [Цифра/факт 3]

ТРЕБОВАНИЯ:
- Сохраняй ВСЕ важные цифры и факты
- Пиши на том же языке, что и видео
- Будь подробным — минимум 800 слов
- Структурируй по логике видео"""


class Summarizer:
    """Transcript summarizer using Ollama."""

    async def summarize(
        self,
        transcript: str,
        metadata: Optional[dict] = None
    ) -> str:
        """
        Create summary of transcript.

        Args:
            transcript: Full transcript text
            metadata: Optional video metadata (title, channel, etc.)

        Returns:
            Summary text
        """
        # Build prompt with context
        prompt_parts = []

        if metadata:
            if metadata.get('title'):
                prompt_parts.append(f"Название: {metadata['title']}")
            if metadata.get('channel'):
                prompt_parts.append(f"Канал: {metadata['channel']}")

            # Add chapters if available
            if metadata.get('chapters'):
                chapters = metadata['chapters']
                prompt_parts.append(f"\nГлавы видео ({len(chapters)}):")
                for ch in chapters:
                    prompt_parts.append(f"  {ch['timestamp']} — {ch['title']}")

        prompt_parts.append(f"\nТранскрипт:\n{transcript}")

        prompt = "\n".join(prompt_parts)

        logger.info(
            "summarization_started",
            transcript_length=len(transcript),
            has_metadata=bool(metadata)
        )

        # Generate summary using selected AI provider
        summary = await ai_client.generate(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
            temperature=settings.TEMPERATURE,
            max_tokens=settings.MAX_SUMMARY_LENGTH
        )

        logger.info("summarization_completed", summary_length=len(summary))

        return summary

    async def summarize_stream(
        self,
        transcript: str,
        metadata: Optional[dict] = None
    ):
        """
        Generate summary with streaming.

        Args:
            transcript: Full transcript text
            metadata: Optional video metadata

        Yields:
            Summary text chunks
        """
        # Build prompt with context
        prompt_parts = []

        if metadata:
            if metadata.get('title'):
                prompt_parts.append(f"Название: {metadata['title']}")
            if metadata.get('channel'):
                prompt_parts.append(f"Канал: {metadata['channel']}")

            # Add chapters if available
            if metadata.get('chapters'):
                chapters = metadata['chapters']
                prompt_parts.append(f"\nГлавы видео ({len(chapters)}):")
                for ch in chapters:
                    prompt_parts.append(f"  {ch['timestamp']} — {ch['title']}")

        prompt_parts.append(f"\nТранскрипт:\n{transcript}")

        prompt = "\n".join(prompt_parts)

        logger.info(
            "summarization_stream_started",
            transcript_length=len(transcript),
            has_metadata=bool(metadata)
        )

        # Stream summary generation using selected AI provider
        async for chunk in ai_client.generate_stream(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
            temperature=settings.TEMPERATURE,
            max_tokens=settings.MAX_SUMMARY_LENGTH
        ):
            yield chunk

        logger.info("summarization_stream_completed")


# Global summarizer instance
summarizer = Summarizer()
