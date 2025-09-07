#!/usr/bin/env python3
"""
Lecture Chunker - разбивка длинных лекций на части для качественного анализа.
Поддерживает передачу контекста между частями.
"""

import re
import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import timedelta

logger = logging.getLogger(__name__)

@dataclass
class ChunkInfo:
    """Информация о части лекции."""
    index: int
    start_time: float  # секунды
    end_time: float    # секунды
    content: str
    char_count: int
    context_start: Optional[float] = None  # начало контекста для следующей части
    last_topic_timing: Optional[str] = None  # последняя тема для контекста

class LectureChunker:
    """
    Класс для разбивки длинных лекций на управляемые части.
    Поддерживает передачу контекста между частями.
    """
    
    def __init__(self, chunk_minutes: int = 50, overlap_minutes: int = 5):
        """
        Args:
            chunk_minutes: Длительность каждой части в минутах
            overlap_minutes: Перекрытие для контекста между частями
        """
        self.chunk_duration = chunk_minutes * 60  # секунды
        self.overlap_duration = overlap_minutes * 60  # секунды
        
    def split_lecture(self, transcript_data: Dict) -> List[ChunkInfo]:
        """
        Разбивает транскрипт на части по временным меткам.
        
        Args:
            transcript_data: Словарь с данными транскрипта (segments и т.д.)
            
        Returns:
            Список частей лекции
        """
        segments = transcript_data.get('segments', [])
        if not segments:
            raise ValueError("Транскрипт не содержит сегментов")
            
        # Вычисляем общую длительность из последнего сегмента
        if segments:
            last_segment = segments[-1]
            total_duration = last_segment['start'] + last_segment.get('duration', 0)
        else:
            total_duration = 0
        logger.info(f"Разбиваю лекцию длительностью {total_duration/60:.1f} минут на части по {self.chunk_duration/60} минут")
        
        chunks = []
        chunk_start = 0
        chunk_index = 0
        
        while chunk_start < total_duration:
            chunk_end = min(chunk_start + self.chunk_duration, total_duration)
            
            # Собираем сегменты для этой части
            chunk_segments = self._get_segments_in_range(segments, chunk_start, chunk_end)
            chunk_content = self._build_chunk_content(chunk_segments)
            
            # Находим последнюю незавершенную тему для контекста
            last_topic_timing = self._extract_last_topic_timing(chunk_segments, chunk_end)
            
            chunk_info = ChunkInfo(
                index=chunk_index,
                start_time=chunk_start,
                end_time=chunk_end,
                content=chunk_content,
                char_count=len(chunk_content),
                last_topic_timing=last_topic_timing
            )
            
            chunks.append(chunk_info)
            
            chunk_start = chunk_end
            chunk_index += 1
            
        logger.info(f"Создано {len(chunks)} частей лекции")
        for i, chunk in enumerate(chunks):
            logger.info(f"  Часть {i+1}: {chunk.start_time/60:.1f}-{chunk.end_time/60:.1f} мин, {chunk.char_count:,} символов")
            
        return chunks
    
    def get_overlap_context(self, transcript_data: Dict, context_start_time: float) -> str:
        """
        Получает контекст из предыдущей части для передачи следующей.
        
        Args:
            transcript_data: Исходные данные транскрипта
            context_start_time: Время начала контекста (секунды)
            
        Returns:
            Текст контекста
        """
        segments = transcript_data.get('segments', [])
        context_end = context_start_time + self.overlap_duration
        
        context_segments = self._get_segments_in_range(segments, context_start_time, context_end)
        context_content = self._build_chunk_content(context_segments, is_context=True)
        
        logger.info(f"Подготовлен контекст: {context_start_time/60:.1f}-{context_end/60:.1f} мин, {len(context_content)} символов")
        
        return context_content
    
    def _get_segments_in_range(self, segments: List[Dict], start_time: float, end_time: float) -> List[Dict]:
        """Получает сегменты в заданном временном диапазоне."""
        result = []
        
        for segment in segments:
            segment_start = segment.get('start', 0)
            segment_duration = segment.get('duration', 1)
            segment_end = segment_start + segment_duration
            
            # Сегмент перекрывается с нужным диапазоном
            if segment_start < end_time and segment_end > start_time:
                result.append(segment)
                
        return result
    
    def _build_chunk_content(self, segments: List[Dict], is_context: bool = False) -> str:
        """Строит текстовое содержимое части из сегментов."""
        if not segments:
            return ""
            
        content = []
        current_time_marker = None
        
        for segment in segments:
            segment_start = segment.get('start', 0)
            segment_text = segment.get('text', '').strip()
            
            # Добавляем временные метки каждые 10 минут
            time_marker_minutes = int(segment_start // 600) * 10  # каждые 10 минут
            if time_marker_minutes != current_time_marker:
                current_time_marker = time_marker_minutes
                hours = time_marker_minutes // 60
                mins = time_marker_minutes % 60
                time_marker = f"[{hours}:{mins:02d}:00]"
                
                if is_context:
                    content.append(f"\n{time_marker} КОНТЕКСТ:")
                else:
                    content.append(f"\n{time_marker}")
                    
            content.append(segment_text)
            
        return " ".join(content).strip()
    
    def _extract_last_topic_timing(self, segments: List[Dict], chunk_end_time: float) -> Optional[str]:
        """
        Находит время начала последней незавершенной темы в части.
        Эвристика: ищем последний значительный переход или начало новой мысли.
        """
        if not segments:
            return None
            
        # Ищем сегменты в последние 10 минут части
        search_start = max(0, chunk_end_time - 600)  # последние 10 минут
        recent_segments = [s for s in segments if s.get('start', 0) >= search_start]
        
        if not recent_segments:
            return None
            
        # Ищем маркеры начала новых тем
        topic_markers = [
            r'(?:итак|теперь|далее|следующий|рассмотрим|перейдем)',
            r'(?:во-первых|во-вторых|в-третьих)',
            r'(?:другой|еще один|также)',
            r'(?:важно|ключевой|основной)',
        ]
        
        combined_pattern = '|'.join(f'({pattern})' for pattern in topic_markers)
        
        # Ищем от конца к началу
        for segment in reversed(recent_segments):
            text = segment.get('text', '').lower()
            if re.search(combined_pattern, text, re.IGNORECASE):
                start_time = segment.get('start', 0)
                hours = int(start_time // 3600)
                minutes = int((start_time % 3600) // 60)
                seconds = int(start_time % 60)
                return f"{hours}:{minutes:02d}:{seconds:02d}"
                
        # Если не нашли маркеры, берем начало последних 5 минут
        fallback_time = chunk_end_time - 300  # 5 минут назад
        hours = int(fallback_time // 3600)
        minutes = int((fallback_time % 3600) // 60)
        seconds = int(fallback_time % 60)
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    
    def format_time(self, seconds: float) -> str:
        """Форматирует время в виде H:MM:SS."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours}:{minutes:02d}:{secs:02d}"
    
    def get_stats(self, chunks: List[ChunkInfo]) -> Dict:
        """Получает статистику по частям."""
        if not chunks:
            return {}
            
        total_chars = sum(chunk.char_count for chunk in chunks)
        avg_chars = total_chars / len(chunks)
        
        return {
            'total_chunks': len(chunks),
            'total_characters': total_chars,
            'average_characters_per_chunk': int(avg_chars),
            'chunk_duration_minutes': self.chunk_duration / 60,
            'overlap_duration_minutes': self.overlap_duration / 60,
            'chunks_info': [
                {
                    'index': chunk.index,
                    'time_range': f"{self.format_time(chunk.start_time)} - {self.format_time(chunk.end_time)}",
                    'characters': chunk.char_count,
                    'last_topic_timing': chunk.last_topic_timing
                }
                for chunk in chunks
            ]
        }