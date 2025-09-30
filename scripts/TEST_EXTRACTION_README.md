# 🧪 Test Extraction Script

Скрипт для тестирования возможностей yt-dlp перед интеграцией в сервис.

## 🚀 Быстрый старт

```bash
# Запуск интерактивного меню
python3 test_extraction.py
```

---

## 📋 Что можно протестировать

### 1. **YouTube транскрипт**
Проверяет наличие субтитров (manual + auto-generated)
```bash
python3 test_extraction.py
# Выбрать: 1
```

### 2. **Скачивание аудио**
Скачивает audio-only версию (конвертирует в MP3)
```bash
python3 test_extraction.py
# Выбрать: 2
# ⚠️ Создаст папку test_audio/
```

### 3. **Свой URL**
Тестируй любую платформу
```bash
python3 test_extraction.py
# Выбрать: 3
# Вставить свой URL
```

### 4. **Список платформ**
Показывает все поддерживаемые платформы
```bash
python3 test_extraction.py
# Выбрать: 4
```

---

## 🌐 Поддерживаемые платформы

✅ **Работают сейчас (1841+ extractors):**
- YouTube (video + music)
- TikTok
- Instagram
- Twitter/X
- SoundCloud
- Spotify
- Reddit
- Vimeo
- Twitch
- Facebook
- Dailymotion
- Bandcamp
- Mixcloud
- Audiomack
- ...и многие другие

---

## 📊 Что показывает скрипт

### Для транскрипта:
- ✅ Title, Channel, Duration
- ✅ Manual subtitles (есть/нет)
- ✅ Auto-generated captions (есть/нет)
- ✅ Доступные языки
- ✅ URL субтитров
- ✅ Наличие аудио

### Для аудио:
- ✅ Качество (bitrate)
- ✅ Формат (MP3, AAC, etc.)
- ✅ Размер файла
- ✅ Прогресс скачивания

---

## 🧪 Примеры тестирования

### YouTube с транскриптом:
```bash
python3 test_extraction.py
1
# Нажать Enter для тест-URL
# или вставить свой: https://www.youtube.com/watch?v=...
```

**Результат:**
```
✅ METADATA:
  Title: Me at the zoo
  Channel: jawed
  Duration: 19 seconds

📝 SUBTITLES:
  Manual subtitles: ✅ Yes
  Auto-generated: ✅ Yes
  Available languages: ['en', 'de']

✅ Found VTT transcript in 'en'

🎵 AUDIO:
  Audio available: ✅ Yes
  Best audio: medium, DRC (129 kbps)
```

---

### Podcasts (SoundCloud, Spotify):
```bash
python3 test_extraction.py
3
https://soundcloud.com/your-podcast
2  # Audio download
y  # Confirm
```

**Результат:**
- Скачает аудио в `test_audio/`
- Покажет metadata (title, duration)

---

### TikTok / Instagram:
```bash
python3 test_extraction.py
3
https://www.tiktok.com/@user/video/123
1  # Transcript check
```

**Результат:**
- Покажет есть ли субтитры
- Если нет → нужен Whisper (Phase 2.2)

---

## 🎯 Что проверять

### ✅ Для интеграции нужно:

1. **Transcript available?**
   - Если ДА → сохраняем сразу
   - Если НЕТ → нужен audio download + Whisper

2. **Audio quality**
   - Проверить bitrate
   - Оптимально: 128-192 kbps

3. **Platform support**
   - Протестировать каждую платформу отдельно
   - Проверить edge cases

---

## 🐛 Troubleshooting

### "No subtitles available"
→ Нормально! Не все видео имеют субтитры
→ Решение: audio download + Whisper

### "Audio download fails"
→ Проверить URL
→ Некоторые платформы требуют cookies/auth

### "Platform not supported"
→ Проверить список: `python3 test_extraction.py` → 4
→ yt-dlp поддерживает 1841+ сайтов

---

## 📝 Результаты тестирования

**Заполни после тестов:**

| Platform | Transcript? | Audio? | Notes |
|----------|-------------|--------|-------|
| YouTube | ✅ | ✅ | Auto-captions work |
| TikTok | ? | ? | Test needed |
| Instagram | ? | ? | Test needed |
| SoundCloud | ? | ✅ | Podcasts |
| Spotify | ? | ? | Test needed |
| Twitter/X | ? | ? | Test needed |

---

## 🚀 Следующие шаги

После успешного тестирования:

1. ✅ Проверили что платформы работают
2. ✅ Поняли когда нужен Whisper
3. → Интегрируем в Content Extractor
4. → Добавляем audio processing (Phase 2.2)

---

## 🧹 Cleanup

```bash
# Удалить тестовые аудио файлы
rm -rf test_audio/

# Удалить скрипт после тестирования
rm test_extraction.py
```