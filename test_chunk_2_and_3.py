#!/usr/bin/env python3
"""
Тест анализа 2-й и 3-й частей с контекстом.
"""

import json
import asyncio
import logging
from datetime import datetime

from chunk_analyzer import ChunkAnalyzer
from lecture_chunker import LectureChunker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_chunk_2_with_context():
    """Тест анализа 2-й части с контекстом из 1-й части."""
    print("🔬 ТЕСТ АНАЛИЗА 2-Й ЧАСТИ С КОНТЕКСТОМ")
    print("="*60)
    
    try:
        # Загружаем данные лекции
        with open('psychology_lecture_transcript.json', 'r', encoding='utf-8') as f:
            lecture_data = json.load(f)
        
        video_info = lecture_data['video_info']
        transcript = lecture_data['transcript']
        
        # Создаем chunker и получаем части
        chunker = LectureChunker(chunk_minutes=50, overlap_minutes=5)
        chunks = chunker.split_lecture(transcript)
        
        chunk_2 = chunks[1]  # вторая часть
        
        print(f"🎥 Видео: {video_info['title']}")
        print(f"📝 Анализируем часть 2: {chunker.format_time(chunk_2.start_time)} - {chunker.format_time(chunk_2.end_time)}")
        print(f"🔤 Символов в части: {chunk_2.char_count:,}")
        print()
        
        # Подготавливаем контент с контекстом из части 1
        # Используем время последней темы из результата анализа части 1
        last_topic_time_1 = "0:40:00"  # из результата части 1
        context_start_seconds = 40 * 60  # 0:40:00 в секундах
        
        # Получаем контекст
        context_content = chunker.get_overlap_context(transcript, context_start_seconds)
        
        # Подготавливаем контент с контекстом
        content_with_context = f"""КОНТЕКСТ ИЗ ПРЕДЫДУЩЕЙ ЧАСТИ (начало темы: {last_topic_time_1}):
{context_content}

ОСНОВНОЙ АНАЛИЗ ТЕКУЩЕЙ ЧАСТИ:
{chunk_2.content}"""
        
        print(f"🔗 Добавлен контекст из части 1:")
        print(f"  Начало контекста: {last_topic_time_1}")
        print(f"  Длина контекста: {len(context_content):,} символов")
        print(f"  Общая длина с контекстом: {len(content_with_context):,} символов")
        print()
        
        # Создаем анализатор и анализируем часть 2 с контекстом
        analyzer = ChunkAnalyzer()
        
        print("🤖 Запускаю анализ части 2 с контекстом...")
        start_time = datetime.now()
        
        chunk_result = await analyzer._analyze_single_chunk(
            content_with_context, chunk_2, "ru"
        )
        
        processing_time = (datetime.now() - start_time).total_seconds()
        
        print("📊 РЕЗУЛЬТАТ АНАЛИЗА ВТОРОЙ ЧАСТИ:")
        print(f"⏱️ Время обработки: {chunk_result.processing_time:.1f} секунд")
        print(f"🎯 Токенов использовано: {chunk_result.tokens_used:,}")
        print(f"📍 Последняя тема: {chunk_result.last_topic_timing}")
        print(f"🔗 Контекст использован: Да")
        print()
        
        print("📝 АНАЛИЗ ЧАСТИ 2:")
        print("-" * 60)
        print(chunk_result.analysis)
        print("-" * 60)
        
        # Сохраняем результат
        save_data = {
            "video_info": video_info,
            "chunk_info": {
                "index": 1,
                "time_range": chunk_result.time_range,
                "char_count": chunk_2.char_count,
                "tokens_used": chunk_result.tokens_used,
                "processing_time": chunk_result.processing_time,
                "last_topic_timing": chunk_result.last_topic_timing,
                "context_provided": True,
                "context_start_time": last_topic_time_1,
                "context_length": len(context_content)
            },
            "analysis": chunk_result.analysis
        }
        
        output_file = f"chunk_analysis_results/psychology_chunk2_with_context_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, ensure_ascii=False, indent=2)
        
        print(f"💾 Результат сохранен в: {output_file}")
        
        return chunk_result.last_topic_timing  # возвращаем для части 3
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        logger.error(f"Chunk 2 test failed: {e}", exc_info=True)
        return None

async def test_chunk_3_with_context(last_topic_time_2):
    """Тест анализа 3-й части с контекстом из 2-й части."""
    print("\n🔬 ТЕСТ АНАЛИЗА 3-Й ЧАСТИ С КОНТЕКСТОМ")
    print("="*60)
    
    try:
        # Загружаем данные лекции
        with open('psychology_lecture_transcript.json', 'r', encoding='utf-8') as f:
            lecture_data = json.load(f)
        
        video_info = lecture_data['video_info']
        transcript = lecture_data['transcript']
        
        # Создаем chunker и получаем части
        chunker = LectureChunker(chunk_minutes=50, overlap_minutes=5)
        chunks = chunker.split_lecture(transcript)
        
        chunk_3 = chunks[2]  # третья часть
        
        print(f"🎥 Видео: {video_info['title']}")
        print(f"📝 Анализируем часть 3: {chunker.format_time(chunk_3.start_time)} - {chunker.format_time(chunk_3.end_time)}")
        print(f"🔤 Символов в части: {chunk_3.char_count:,}")
        print()
        
        if last_topic_time_2:
            # Парсим время в секунды
            time_parts = last_topic_time_2.split(':')
            context_start_seconds = int(time_parts[0]) * 3600 + int(time_parts[1]) * 60 + int(time_parts[2])
            
            # Получаем контекст
            context_content = chunker.get_overlap_context(transcript, context_start_seconds)
            
            # Подготавливаем контент с контекстом
            content_with_context = f"""КОНТЕКСТ ИЗ ПРЕДЫДУЩЕЙ ЧАСТИ (начало темы: {last_topic_time_2}):
{context_content}

ОСНОВНОЙ АНАЛИЗ ТЕКУЩЕЙ ЧАСТИ:
{chunk_3.content}"""
            
            print(f"🔗 Добавлен контекст из части 2:")
            print(f"  Начало контекста: {last_topic_time_2}")
            print(f"  Длина контекста: {len(context_content):,} символов")
            print(f"  Общая длина с контекстом: {len(content_with_context):,} символов")
            
        else:
            content_with_context = chunk_3.content
            print("⚠️ Контекст из части 2 недоступен, анализируем без контекста")
        
        print()
        
        # Создаем анализатор и анализируем часть 3
        analyzer = ChunkAnalyzer()
        
        print("🤖 Запускаю анализ части 3 с контекстом...")
        start_time = datetime.now()
        
        chunk_result = await analyzer._analyze_single_chunk(
            content_with_context, chunk_3, "ru"
        )
        
        processing_time = (datetime.now() - start_time).total_seconds()
        
        print("📊 РЕЗУЛЬТАТ АНАЛИЗА ТРЕТЬЕЙ ЧАСТИ:")
        print(f"⏱️ Время обработки: {chunk_result.processing_time:.1f} секунд")
        print(f"🎯 Токенов использовано: {chunk_result.tokens_used:,}")
        print(f"📍 Последняя тема: {chunk_result.last_topic_timing}")
        print(f"🔗 Контекст использован: {'Да' if last_topic_time_2 else 'Нет'}")
        print()
        
        print("📝 АНАЛИЗ ЧАСТИ 3:")
        print("-" * 60)
        print(chunk_result.analysis)
        print("-" * 60)
        
        # Сохраняем результат
        save_data = {
            "video_info": video_info,
            "chunk_info": {
                "index": 2,
                "time_range": chunk_result.time_range,
                "char_count": chunk_3.char_count,
                "tokens_used": chunk_result.tokens_used,
                "processing_time": chunk_result.processing_time,
                "last_topic_timing": chunk_result.last_topic_timing,
                "context_provided": bool(last_topic_time_2),
                "context_start_time": last_topic_time_2 if last_topic_time_2 else None,
                "context_length": len(context_content) if last_topic_time_2 else 0
            },
            "analysis": chunk_result.analysis
        }
        
        output_file = f"chunk_analysis_results/psychology_chunk3_with_context_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, ensure_ascii=False, indent=2)
        
        print(f"💾 Результат сохранен в: {output_file}")
        
        return chunk_result
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        logger.error(f"Chunk 3 test failed: {e}", exc_info=True)
        return None

async def main():
    """Последовательный анализ частей 2 и 3 с передачей контекста."""
    print("🚀 АНАЛИЗ ЧАСТЕЙ 2 И 3 С ПЕРЕДАЧЕЙ КОНТЕКСТА")
    print("="*60)
    
    # Анализируем часть 2 с контекстом из части 1
    last_topic_time_2 = await test_chunk_2_with_context()
    
    if last_topic_time_2:
        # Анализируем часть 3 с контекстом из части 2
        await test_chunk_3_with_context(last_topic_time_2)
    else:
        print("❌ Не удалось получить контекст из части 2 для части 3")

if __name__ == "__main__":
    asyncio.run(main())