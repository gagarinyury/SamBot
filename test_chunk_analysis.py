#!/usr/bin/env python3
"""
Тест системы анализа лекций по частям.
Тестируем на данных психологической лекции.
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

async def test_chunking_only():
    """Тестируем только разбивку на части без анализа."""
    print("🔬 ТЕСТИРОВАНИЕ РАЗБИВКИ ЛЕКЦИИ НА ЧАСТИ")
    print("="*60)
    
    try:
        # Загружаем данные лекции
        print("📂 Загружаю транскрипт лекции...")
        with open('psychology_lecture_transcript.json', 'r', encoding='utf-8') as f:
            lecture_data = json.load(f)
        
        video_info = lecture_data['video_info']
        transcript = lecture_data['transcript']
        
        print(f"🎥 Видео: {video_info['title']}")
        print(f"⏱️ Длительность: {video_info['duration_formatted']}")
        print(f"📝 Символов: {transcript['char_count']:,}")
        print()
        
        # Создаем chunker и разбиваем
        chunker = LectureChunker(chunk_minutes=50, overlap_minutes=5)
        chunks = chunker.split_lecture(transcript)
        
        # Получаем статистику
        stats = chunker.get_stats(chunks)
        
        print("📊 РЕЗУЛЬТАТ РАЗБИВКИ:")
        print(f"  Всего частей: {stats['total_chunks']}")
        print(f"  Длительность частей: {stats['chunk_duration_minutes']} минут")
        print(f"  Перекрытие: {stats['overlap_duration_minutes']} минут")
        print(f"  Общее количество символов: {stats['total_characters']:,}")
        print(f"  Среднее символов на часть: {stats['average_characters_per_chunk']:,}")
        print()
        
        print("📝 ДЕТАЛИЗАЦИЯ ПО ЧАСТЯМ:")
        for chunk_info in stats['chunks_info']:
            print(f"  Часть {chunk_info['index'] + 1}: {chunk_info['time_range']}")
            print(f"    Символов: {chunk_info['characters']:,}")
            print(f"    Последняя тема: {chunk_info['last_topic_timing']}")
            print()
        
        # Тестируем получение контекста
        if len(chunks) > 1:
            print("🔗 ТЕСТИРОВАНИЕ КОНТЕКСТА МЕЖДУ ЧАСТЯМИ:")
            chunk2 = chunks[1]
            if chunk2.last_topic_timing:
                context_start = chunker._parse_timing_to_seconds(chunk2.last_topic_timing) if hasattr(chunker, '_parse_timing_to_seconds') else 0
                
                # Для тестирования берем время из первой части
                context_start = chunks[0].end_time - 300  # 5 минут назад от конца первой части
                
                context_content = chunker.get_overlap_context(transcript, context_start)
                print(f"  Контекст для части 2:")
                print(f"  Начало контекста: {chunker.format_time(context_start)}")
                print(f"  Длина контекста: {len(context_content)} символов")
                print(f"  Превью контекста: {context_content[:200]}...")
                print()
        
        # Сохраняем результат для анализа
        save_data = {
            "video_info": video_info,
            "chunking_stats": stats,
            "chunks_preview": []
        }
        
        # Добавляем превью первых 500 символов каждой части
        for i, chunk in enumerate(chunks):
            save_data["chunks_preview"].append({
                "index": i,
                "time_range": f"{chunker.format_time(chunk.start_time)} - {chunker.format_time(chunk.end_time)}",
                "char_count": chunk.char_count,
                "preview": chunk.content[:500] + "..." if len(chunk.content) > 500 else chunk.content,
                "last_topic_timing": chunk.last_topic_timing
            })
        
        # Сохраняем в отдельную папку
        output_file = f"chunk_analysis_results/psychology_chunking_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, ensure_ascii=False, indent=2)
        
        print(f"💾 Результат тестирования сохранен в: {output_file}")
        print("✅ Тестирование разбивки завершено успешно!")
        
    except Exception as e:
        print(f"❌ Ошибка тестирования: {e}")
        logger.error(f"Chunking test failed: {e}", exc_info=True)

async def test_full_analysis():
    """Полный тест анализа по частям."""
    print("🚀 ПОЛНЫЙ ТЕСТ АНАЛИЗА ПО ЧАСТЯМ")
    print("="*60)
    
    try:
        # Загружаем данные лекции
        print("📂 Загружаю транскрипт лекции...")
        with open('psychology_lecture_transcript.json', 'r', encoding='utf-8') as f:
            lecture_data = json.load(f)
        
        video_info = lecture_data['video_info']
        transcript = lecture_data['transcript']
        
        print(f"🎥 Видео: {video_info['title']}")
        print(f"⏱️ Длительность: {video_info['duration_formatted']}")
        print(f"📝 Символов: {transcript['char_count']:,}")
        print()
        
        # Создаем анализатор
        analyzer = ChunkAnalyzer(chunk_minutes=50, overlap_minutes=5)
        
        print("🎯 Запускаю полный анализ по частям...")
        start_time = datetime.now()
        
        # Анализируем
        result = await analyzer.analyze_lecture(transcript, video_info, target_language="ru")
        
        total_time = (datetime.now() - start_time).total_seconds()
        
        print("="*60)
        print("📊 РЕЗУЛЬТАТ АНАЛИЗА")
        print("="*60)
        
        print(f"✅ Анализ завершен успешно!")
        print(f"⏱️ Общее время: {total_time:.1f} секунд")
        print(f"🎯 Всего токенов: {result.total_tokens:,}")
        print(f"📊 Частей проанализировано: {len(result.chunks_analysis)}")
        print()
        
        print("📝 АНАЛИЗ ПО ЧАСТЯМ:")
        for i, chunk_result in enumerate(result.chunks_analysis):
            print(f"  Часть {i+1}: {chunk_result.time_range}")
            print(f"    Токенов: {chunk_result.tokens_used:,}")
            print(f"    Время: {chunk_result.processing_time:.1f}с")
            print(f"    Контекст: {'Да' if chunk_result.context_provided else 'Нет'}")
            print(f"    Последняя тема: {chunk_result.last_topic_timing}")
            print()
        
        print("🎨 ФИНАЛЬНОЕ РЕЗЮМЕ:")
        print("-" * 60)
        print(result.combined_summary)
        print("-" * 60)
        
        # Сохраняем результат в отдельную папку
        output_file = f"chunk_analysis_results/psychology_full_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        output_file = analyzer.save_result(result, output_file)
        print(f"💾 Полный результат сохранен в: {output_file}")
        
    except Exception as e:
        print(f"❌ Ошибка анализа: {e}")
        logger.error(f"Full analysis test failed: {e}", exc_info=True)

async def test_single_chunk():
    """Тест анализа только первой части."""
    print("🔬 ТЕСТ АНАЛИЗА ОДНОЙ ЧАСТИ")
    print("="*60)
    
    try:
        # Загружаем данные лекции
        print("📂 Загружаю транскрипт лекции...")
        with open('psychology_lecture_transcript.json', 'r', encoding='utf-8') as f:
            lecture_data = json.load(f)
        
        video_info = lecture_data['video_info']
        transcript = lecture_data['transcript']
        
        # Создаем chunker и берем первую часть
        chunker = LectureChunker(chunk_minutes=50, overlap_minutes=5)
        chunks = chunker.split_lecture(transcript)
        
        first_chunk = chunks[0]
        
        print(f"🎥 Видео: {video_info['title']}")
        print(f"📝 Анализируем часть 1: {chunker.format_time(first_chunk.start_time)} - {chunker.format_time(first_chunk.end_time)}")
        print(f"🔤 Символов в части: {first_chunk.char_count:,}")
        print()
        
        # Создаем анализатор и анализируем только первую часть
        analyzer = ChunkAnalyzer()
        
        chunk_result = await analyzer._analyze_single_chunk(
            first_chunk.content, first_chunk, "ru"
        )
        
        print("📊 РЕЗУЛЬТАТ АНАЛИЗА ПЕРВОЙ ЧАСТИ:")
        print(f"⏱️ Время обработки: {chunk_result.processing_time:.1f} секунд")
        print(f"🎯 Токенов использовано: {chunk_result.tokens_used:,}")
        print(f"📍 Последняя тема: {chunk_result.last_topic_timing}")
        print()
        
        print("📝 АНАЛИЗ:")
        print("-" * 60)
        print(chunk_result.analysis)
        print("-" * 60)
        
        # Сохраняем результат
        save_data = {
            "video_info": video_info,
            "chunk_info": {
                "index": first_chunk.index,
                "time_range": chunk_result.time_range,
                "char_count": first_chunk.char_count,
                "tokens_used": chunk_result.tokens_used,
                "processing_time": chunk_result.processing_time,
                "last_topic_timing": chunk_result.last_topic_timing
            },
            "analysis": chunk_result.analysis
        }
        
        output_file = f"chunk_analysis_results/psychology_single_chunk_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, ensure_ascii=False, indent=2)
        
        print(f"💾 Результат сохранен в: {output_file}")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        logger.error(f"Single chunk test failed: {e}", exc_info=True)

async def main():
    """Главная функция для выбора теста."""
    print("🧪 ТЕСТИРОВАНИЕ СИСТЕМЫ АНАЛИЗА ПО ЧАСТЯМ")
    print("="*60)
    print("1. Тест разбивки на части (быстро)")
    print("2. Тест анализа одной части (средне)")  
    print("3. Полный тест анализа всех частей (медленно, дорого)")
    print()
    
    choice = input("Выберите тест (1-3): ").strip()
    
    if choice == "1":
        await test_chunking_only()
    elif choice == "2":
        await test_single_chunk()
    elif choice == "3":
        await test_full_analysis()
    else:
        print("❌ Неверный выбор. Запускаю тест разбивки...")
        await test_chunking_only()

if __name__ == "__main__":
    asyncio.run(main())