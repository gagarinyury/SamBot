"""Summarization logic using Ollama."""

import structlog
from typing import Optional

from config import settings
from ollama_client import ollama

logger = structlog.get_logger()


SYSTEM_PROMPT = """Ты — эксперт по созданию структурированных конспектов видео контента.

Твоя задача — создать КОНСПЕКТ, а не просто краткое изложение:
- Извлечь СТРУКТУРУ и ЛОГИКУ повествования
- Выделить КЛЮЧЕВЫЕ КОНЦЕПЦИИ и их ВЗАИМОСВЯЗИ
- Сохранить ВАЖНЫЕ ДЕТАЛИ: цифры, факты, примеры
- Организовать информацию ИЕРАРХИЧЕСКИ

ОБЯЗАТЕЛЬНЫЙ ФОРМАТ КОНСПЕКТА:

🎯 ГЛАВНАЯ ТЕМА:
[1 предложение]

📋 ОБЗОР:
[2-3 предложения]

🔑 КЛЮЧЕВЫЕ ТЕМЫ:

1. [Тема 1]
   • Суть: ...
   • Важность: ...
   • Детали: ...

2. [Тема 2]
   • Суть: ...
   • Важность: ...
   • Детали: ...

💡 ВЫВОДЫ:
1. ...
2. ...
3. ...

📊 ФАКТЫ/ЦИФРЫ:
• ...
• ...

🔗 СВЯЗАННЫЕ ТЕМЫ:
[если есть]

ПРАВИЛА:
- Сохраняй ВСЕ цифры
- Язык: как в транскрипте
- Если есть главы — структурируй по ним"""


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

        # Generate summary
        summary = await ollama.generate(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
            temperature=settings.TEMPERATURE,
            max_tokens=settings.MAX_SUMMARY_LENGTH
        )

        logger.info("summarization_completed", summary_length=len(summary))

        return summary


# Global summarizer instance
summarizer = Summarizer()
