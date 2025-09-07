#!/usr/bin/env python3
"""
Chunk Analyzer - анализ лекций по частям с передачей контекста.
Интегрируется с существующей системой DeepSeek.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict

from lecture_chunker import LectureChunker, ChunkInfo
from summarizers.deepseek import get_summarizer, SummaryResponse
from config import get_config

logger = logging.getLogger(__name__)

@dataclass
class ChunkAnalysisResult:
    """Результат анализа одной части лекции."""
    chunk_index: int
    time_range: str
    analysis: str
    tokens_used: int
    processing_time: float
    last_topic_timing: Optional[str] = None
    context_provided: bool = False

@dataclass
class LectureAnalysisResult:
    """Финальный результат анализа всей лекции."""
    video_info: Dict
    chunks_analysis: List[ChunkAnalysisResult]
    combined_summary: str
    total_tokens: int
    total_processing_time: float
    chunk_stats: Dict
    analysis_date: str

class ChunkAnalyzer:
    """
    Анализатор лекций по частям с передачей контекста между частями.
    """
    
    def __init__(self, chunk_minutes: int = 50, overlap_minutes: int = 5):
        self.chunker = LectureChunker(chunk_minutes, overlap_minutes)
        self.config = get_config()
        
    async def analyze_lecture(self, transcript_data: Dict, video_info: Dict, 
                            target_language: str = "ru") -> LectureAnalysisResult:
        """
        Полный анализ лекции по частям.
        
        Args:
            transcript_data: Данные транскрипта с сегментами
            video_info: Информация о видео
            target_language: Язык анализа
            
        Returns:
            Результат анализа всей лекции
        """
        start_time = datetime.now()
        logger.info(f"🎓 Начинаю анализ лекции по частям: {video_info.get('title', 'Unknown')}")
        
        # Разбиваем лекцию на части
        chunks = self.chunker.split_lecture(transcript_data)
        chunk_stats = self.chunker.get_stats(chunks)
        
        logger.info(f"📊 Создано {len(chunks)} частей для анализа")
        
        # Анализируем каждую часть
        chunk_results = []
        total_tokens = 0
        
        for i, chunk in enumerate(chunks):
            logger.info(f"🔍 Анализирую часть {i+1}/{len(chunks)}: {self.chunker.format_time(chunk.start_time)} - {self.chunker.format_time(chunk.end_time)}")
            
            # Подготавливаем контент с контекстом
            content_with_context = await self._prepare_chunk_content(
                chunk, transcript_data, chunk_results
            )
            
            # Анализируем часть
            chunk_result = await self._analyze_single_chunk(
                content_with_context, chunk, target_language
            )
            
            chunk_results.append(chunk_result)
            total_tokens += chunk_result.tokens_used
            
            logger.info(f"✅ Часть {i+1} завершена: {chunk_result.tokens_used} токенов, {chunk_result.processing_time:.1f}с")
        
        # Объединяем результаты
        combined_summary = await self._combine_chunk_results(chunk_results, target_language)
        
        total_processing_time = (datetime.now() - start_time).total_seconds()
        
        result = LectureAnalysisResult(
            video_info=video_info,
            chunks_analysis=chunk_results,
            combined_summary=combined_summary,
            total_tokens=total_tokens,
            total_processing_time=total_processing_time,
            chunk_stats=chunk_stats,
            analysis_date=datetime.now().isoformat()
        )
        
        logger.info(f"🏁 Анализ завершен: {total_tokens:,} токенов, {total_processing_time:.1f}с")
        
        return result
    
    async def _prepare_chunk_content(self, chunk: ChunkInfo, transcript_data: Dict, 
                                   previous_results: List[ChunkAnalysisResult]) -> str:
        """Подготавливает контент части с контекстом предыдущей части."""
        content = chunk.content
        
        # Добавляем контекст из предыдущей части
        if previous_results and chunk.index > 0:
            prev_result = previous_results[-1]
            
            # Извлекаем время начала контекста
            if prev_result.last_topic_timing:
                context_start_time = self._parse_timing_to_seconds(prev_result.last_topic_timing)
                
                # Получаем контекст
                context_content = self.chunker.get_overlap_context(
                    transcript_data, context_start_time
                )
                
                if context_content:
                    content = f"""КОНТЕКСТ ИЗ ПРЕДЫДУЩЕЙ ЧАСТИ (начало темы: {prev_result.last_topic_timing}):
{context_content}

ОСНОВНОЙ АНАЛИЗ ТЕКУЩЕЙ ЧАСТИ:
{chunk.content}"""
                    
                    logger.info(f"📎 Добавлен контекст для части {chunk.index + 1}")
        
        return content
    
    async def _analyze_single_chunk(self, content: str, chunk: ChunkInfo, 
                                   target_language: str) -> ChunkAnalysisResult:
        """Анализирует одну часть лекции."""
        chunk_start_time = datetime.now()
        
        # Получаем суммаризатор
        summarizer = get_summarizer()
        
        # Создаем специальный промпт для части лекции
        analysis_prompt = await self._get_chunk_analysis_prompt(target_language, chunk.index + 1)
        
        # Анализируем
        analysis_text, tokens_used = await summarizer._generate_summary_with_retry(
            content=content,
            prompt=analysis_prompt,
            target_language=target_language
        )
        
        processing_time = (datetime.now() - chunk_start_time).total_seconds()
        
        # Извлекаем время последней темы для следующей части
        last_topic_timing = self._extract_last_topic_from_analysis(analysis_text)
        
        return ChunkAnalysisResult(
            chunk_index=chunk.index,
            time_range=f"{self.chunker.format_time(chunk.start_time)} - {self.chunker.format_time(chunk.end_time)}",
            analysis=analysis_text,
            tokens_used=tokens_used,
            processing_time=processing_time,
            last_topic_timing=last_topic_timing or chunk.last_topic_timing,
            context_provided="КОНТЕКСТ ИЗ ПРЕДЫДУЩЕЙ ЧАСТИ" in content
        )
    
    async def _combine_chunk_results(self, chunk_results: List[ChunkAnalysisResult], 
                                   target_language: str) -> str:
        """Объединяет результаты анализа частей в финальное резюме."""
        logger.info("🎨 Объединяю результаты всех частей в финальное резюме")
        
        # Подготавливаем контент для объединения
        combined_content = ""
        for i, result in enumerate(chunk_results):
            combined_content += f"""
ЧАСТЬ {i+1} ({result.time_range}):
{result.analysis}

"""
        
        # Создаем промпт для объединения
        combining_prompt = await self._get_combining_prompt(target_language)
        
        # Получаем суммаризатор и объединяем
        summarizer = get_summarizer()
        final_summary, _ = await summarizer._generate_summary_with_retry(
            content=combined_content,
            prompt=combining_prompt,
            target_language=target_language
        )
        
        return final_summary
    
    async def _get_chunk_analysis_prompt(self, target_language: str, chunk_number: int) -> str:
        """Создает промпт для анализа части лекции."""
        if target_language == "ru":
            return f"""Проанализируй ЧАСТЬ {chunk_number} лекции максимально подробно.

ВАЖНЫЕ ТРЕБОВАНИЯ:
1. Это часть длинной лекции - анализируй подробно все темы и концепции
2. Если есть КОНТЕКСТ из предыдущей части - учитывай его для понимания
3. ОБЯЗАТЕЛЬНО указывай временные метки для важных тем в формате [H:MM:SS]
4. В конце ОБЯЗАТЕЛЬНО укажи: ПОСЛЕДНЯЯ_ТЕМА_НАЧАЛАСЬ: [H:MM:SS] (время начала незавершенной темы)

КОНТЕНТ ДЛЯ АНАЛИЗА:
{{content}}

Создай детальный анализ этой части лекции с временными метками важных моментов.
Включи все ключевые концепции, примеры, объяснения.
Сохрани академический стиль и научную точность."""

        else:
            return f"""Analyze PART {chunk_number} of the lecture in maximum detail.

IMPORTANT REQUIREMENTS:
1. This is part of a long lecture - analyze all topics and concepts thoroughly
2. If there's CONTEXT from previous part - use it for understanding
3. MUST include timing marks for important topics in format [H:MM:SS]  
4. At the end MUST specify: LAST_TOPIC_STARTED: [H:MM:SS] (start time of unfinished topic)

CONTENT FOR ANALYSIS:
{{content}}

Create detailed analysis of this lecture part with timing marks for important moments.
Include all key concepts, examples, explanations.
Maintain academic style and scientific accuracy."""
    
    async def _get_combining_prompt(self, target_language: str) -> str:
        """Создает промпт для объединения частей."""
        if target_language == "ru":
            return """Объедини анализы всех частей лекции в ЕДИНОЕ СТРУКТУРИРОВАННОЕ РЕЗЮМЕ.

ПОЛУЧЕННЫЕ АНАЛИЗЫ ЧАСТЕЙ:
{content}

ТРЕБОВАНИЯ:
1. Создай ЦЕЛЬНОЕ резюме всей лекции (не просто склейку частей)
2. Сохрани все важные временные метки из частей
3. Убери дублирования между частями
4. Создай логическую структуру всей лекции

ФОРМАТ ФИНАЛЬНОГО РЕЗЮМЕ:
ГЛАВНОЕ: (основная идея лекции в 1-2 предложениях)

СТРУКТУРА ЛЕКЦИИ:
• [0:XX:XX] Тема 1: краткое описание
• [X:XX:XX] Тема 2: краткое описание
• [X:XX:XX] Тема 3: краткое описание

КЛЮЧЕВЫЕ МОМЕНТЫ:
• Концепция 1 [время] - объяснение
• Концепция 2 [время] - объяснение
• Концепция 3 [время] - объяснение

ПОДРОБНЫЙ АНАЛИЗ:
[Детальное изложение всех тем с временными метками]

ВЫВОДЫ:
[Основные заключения лекции]"""

        else:
            return """Combine all lecture part analyses into a UNIFIED STRUCTURED SUMMARY.

RECEIVED PART ANALYSES:
{content}

REQUIREMENTS:
1. Create UNIFIED summary of entire lecture (not just concatenation)
2. Preserve all important timing marks from parts
3. Remove duplications between parts
4. Create logical structure of entire lecture

FINAL SUMMARY FORMAT:
MAIN POINT: (main idea of lecture in 1-2 sentences)

LECTURE STRUCTURE:
• [0:XX:XX] Topic 1: brief description
• [X:XX:XX] Topic 2: brief description
• [X:XX:XX] Topic 3: brief description

KEY MOMENTS:
• Concept 1 [time] - explanation
• Concept 2 [time] - explanation
• Concept 3 [time] - explanation

DETAILED ANALYSIS:
[Detailed coverage of all topics with timing marks]

CONCLUSIONS:
[Main lecture conclusions]"""
    
    def _parse_timing_to_seconds(self, timing_str: str) -> float:
        """Парсит строку времени в секунды."""
        try:
            parts = timing_str.split(':')
            if len(parts) == 3:
                hours, minutes, seconds = parts
                return int(hours) * 3600 + int(minutes) * 60 + int(seconds)
            elif len(parts) == 2:
                minutes, seconds = parts
                return int(minutes) * 60 + int(seconds)
            else:
                return float(parts[0])
        except:
            logger.warning(f"Не удалось распарсить время: {timing_str}")
            return 0.0
    
    def _extract_last_topic_from_analysis(self, analysis_text: str) -> Optional[str]:
        """Извлекает время начала последней темы из анализа."""
        import re
        
        # Ищем паттерн ПОСЛЕДНЯЯ_ТЕМА_НАЧАЛАСЬ: [время]
        pattern = r'ПОСЛЕДНЯЯ_ТЕМА_НАЧАЛАСЬ:\s*\[?([0-9:]+)\]?'
        match = re.search(pattern, analysis_text, re.IGNORECASE)
        
        if match:
            return match.group(1)
        
        # Альтернативный поиск - последняя временная метка в тексте
        pattern = r'\[(\d{1,2}:\d{2}:\d{2})\]'
        matches = re.findall(pattern, analysis_text)
        
        if matches:
            return matches[-1]  # последняя найденная метка
            
        return None

    def save_result(self, result: LectureAnalysisResult, output_file: Optional[str] = None) -> str:
        """Сохраняет результат анализа в файл."""
        if not output_file:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = f"chunk_analysis_results/lecture_chunk_analysis_{timestamp}.json"
        
        # Подготавливаем данные для сохранения
        save_data = {
            "video_info": result.video_info,
            "analysis_info": {
                "total_chunks": len(result.chunks_analysis),
                "total_tokens": result.total_tokens,
                "total_processing_time": result.total_processing_time,
                "analysis_date": result.analysis_date,
                **result.chunk_stats
            },
            "chunks_analysis": [asdict(chunk) for chunk in result.chunks_analysis],
            "combined_summary": result.combined_summary
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"💾 Результат сохранен в: {output_file}")
        return output_file