# SamBot - Smart Summarizer Bot

🤖 Бот-саммарайзер который создает умные краткие изложения YouTube видео и веб-статей используя DeepSeek AI.

## ✨ Возможности

### 📹 YouTube Саммари
- Извлечение транскриптов через `youtube-transcript-api`
- Поддержка автоматических субтитров
- Обработка видео на разных языках
- Умные саммари через DeepSeek AI

### 🌐 Веб-страницы Саммари  
- Извлечение основного контента статей
- Очистка от рекламы и навигации
- Поддержка JavaScript-страниц
- Генерация структурированных саммари

## 🛠️ Технологический стек

- **Python 3.8+**
- **DeepSeek AI** - генерация саммари
- **youtube-transcript-api** - YouTube транскрипты
- **newspaper3k** - парсинг веб-статей  
- **BeautifulSoup4** - резервный парсинг
- **Telegram Bot API** - интерфейс бота

## 🚀 Установка

```bash
# Клонирование репозитория
git clone https://github.com/gagarinyury/SamBot.git
cd SamBot

# Создание виртуального окружения
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate  # Windows

# Установка зависимостей
pip install -r requirements.txt

# Настройка переменных окружения
cp .env.example .env
# Отредактировать .env с вашими API ключами
```

## ⚙️ Конфигурация

Создайте файл `.env`:
```env
DEEPSEEK_API_KEY=your_deepseek_api_key
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
```

## 📖 Использование

```bash
# Запуск бота
python bot.py
```

Отправьте боту:
- 🔗 Ссылку на YouTube видео
- 🔗 Ссылку на веб-статью
- 📝 Текст для саммари

## 📁 Структура проекта

```
SamBot/
├── bot.py              # Главный файл бота
├── extractors/         # Модули извлечения контента
│   ├── youtube.py      # YouTube транскрипты
│   └── web.py          # Веб-страницы
├── summarizers/        # AI саммарайзеры
│   └── deepseek.py     # DeepSeek интеграция
├── utils/              # Утилиты
│   └── helpers.py      # Вспомогательные функции
├── config.py           # Конфигурация
├── requirements.txt    # Зависимости
└── README.md          # Документация
```

## 🔧 Разработка

Проект находится в активной разработке. Планируемые функции:
- [ ] Веб-интерфейс
- [ ] Поддержка больше языков
- [ ] Экспорт саммари в разные форматы
- [ ] Интеграция с другими AI моделями

## 📄 Лицензия

MIT License

## 👨‍💻 Автор

[@gagarinyury](https://github.com/gagarinyury)