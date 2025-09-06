"""
SamBot - YouTube Summarizer with Aiogram
User-friendly bot for YouTube video summarization with timestamps and beautiful UI.
"""

import asyncio
import logging
import re
import time
import json
from typing import Optional, Dict, Any
from urllib.parse import urlparse, parse_qs

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    InlineKeyboardMarkup, 
    InlineKeyboardButton, 
    CallbackQuery,
    ReplyKeyboardMarkup,
    KeyboardButton
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.utils.formatting import Text, ExpandableBlockQuote, Bold, Code, Italic, Spoiler
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

from config import get_config
from extractors.youtube import extract_youtube_content, YouTubeVideoInfo
from summarizers.deepseek import summarize_content, SummaryLength
from services.youtube_service import YouTubeService
from services.summarizer_service import SummarizerService

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class SummaryStates(StatesGroup):
    waiting_for_url = State()

class YouTubeSamBot:
    """
    YouTube-focused SamBot with beautiful UI and timestamp support.
    """
    
    def __init__(self):
        self.config = get_config()
        self.bot = Bot(token=self.config.telegram.bot_token)
        self.storage = MemoryStorage()
        self.dp = Dispatcher(storage=self.storage)
        
        # User settings (in-memory for simplicity)
        self.user_settings = {}
        
        # Initialize services
        self.youtube_service = YouTubeService()
        self.summarizer_service = SummarizerService()
        
        # Language settings
        self.languages = {
            'fr': {'name': 'Français', 'emoji': '🇫🇷', 'flag': 'французском'},
            'en': {'name': 'English', 'emoji': '🇬🇧', 'flag': 'английском'},
            'ru': {'name': 'Русский', 'emoji': '🇷🇺', 'flag': 'русском'}
        }
        
        # Summary length settings
        self.summary_types = {
            'brief': {'name': 'Краткое', 'emoji': '📋', 'desc': '2-3 предложения'},
            'detailed': {'name': 'Полное', 'emoji': '📄', 'desc': 'подробное резюме'}
        }
        
        self._setup_handlers()
        logger.info("YouTubeSamBot initialized successfully")
    
    def _setup_handlers(self):
        """Setup all bot handlers."""
        self.dp.message(CommandStart())(self.cmd_start)
        self.dp.message(Command("help"))(self.cmd_help)
        self.dp.message(F.text.contains("youtube.com") | F.text.contains("youtu.be"))(self.handle_youtube_url)
        self.dp.message(F.text == "⚙️ Настройки")(self.show_settings)
        self.dp.message(F.text == "❓ Помощь")(self.cmd_help)
        self.dp.message(F.text)(self.handle_text_message)
        
        # Callback handlers
        self.dp.callback_query(F.data.startswith("lang_"))(self.callback_language)
        self.dp.callback_query(F.data.startswith("summary_"))(self.callback_summary_type)
        self.dp.callback_query(F.data.startswith("process_"))(self.callback_process_video)
        self.dp.callback_query(F.data.startswith("ai_resume_"))(self.callback_ai_resume)
        self.dp.callback_query(F.data == "settings")(self.callback_settings)
        self.dp.callback_query(F.data == "change_lang")(self.callback_change_language)
        self.dp.callback_query(F.data == "change_summary")(self.callback_change_summary)
        self.dp.callback_query(F.data == "new_video")(self.callback_new_video)
        self.dp.callback_query(F.data == "back_to_menu")(self.callback_back_to_menu)
    
    def get_main_keyboard(self) -> ReplyKeyboardMarkup:
        """Get main menu keyboard."""
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [
                    KeyboardButton(text="🎥 YouTube"),
                    KeyboardButton(text="⚙️ Настройки"),
                    KeyboardButton(text="❓ Помощь")
                ]
            ],
            resize_keyboard=True,
            one_time_keyboard=False
        )
        return keyboard
    
    def get_user_settings(self, user_id: int) -> Dict[str, Any]:
        """Get user settings with defaults."""
        if user_id not in self.user_settings:
            self.user_settings[user_id] = {
                'language': 'ru',  # Default to Russian
                'summary_type': 'detailed'  # Default to detailed
            }
        return self.user_settings[user_id]
    
    async def cmd_start(self, message: types.Message):
        """Handle /start command."""
        user_id = message.from_user.id
        user_name = message.from_user.first_name or "друг"
        
        # Initialize user settings
        self.get_user_settings(user_id)
        
        welcome_text = (
            f"🎉 <b>Привет, {user_name}!</b>\n\n"
            f"🎥 Я <b>SamBot</b> — твой помощник для создания резюме YouTube видео!\n\n"
            f"<b>🚀 Что я умею:</b>\n"
            f"📹 Анализировать YouTube видео\n"
            f"🕐 Извлекать субтитры с таймингами\n"
            f"🤖 Создавать умные резюме на 3 языках\n"
            f"⚡ Показывать ключевые моменты с временными метками\n\n"
            f"<b>📱 Просто отправь мне ссылку на YouTube!</b>\n\n"
            f"💡 <i>Используй меню ниже для навигации</i>"
        )
        
        await message.answer(
            welcome_text,
            parse_mode="HTML",
            reply_markup=self.get_main_keyboard()
        )
    
    async def cmd_help(self, message: types.Message):
        """Handle help command."""
        help_text = (
            "🆘 <b>Справка по SamBot</b>\n\n"
            "<b>🎯 Как использовать:</b>\n"
            "1️⃣ Отправь ссылку на YouTube видео\n"
            "2️⃣ Выбери язык и тип резюме\n"
            "3️⃣ Получи резюме с таймингами!\n\n"
            "<b>🔗 Поддерживаемые ссылки:</b>\n"
            "• youtube.com/watch?v=...\n"
            "• youtu.be/...\n"
            "• m.youtube.com/...\n\n"
            "<b>🌐 Языки резюме:</b>\n"
            f"{self.languages['ru']['emoji']} Русский\n"
            f"{self.languages['en']['emoji']} English\n"
            f"{self.languages['fr']['emoji']} Français\n\n"
            "<b>📋 Типы резюме:</b>\n"
            f"{self.summary_types['brief']['emoji']} Краткое — {self.summary_types['brief']['desc']}\n"
            f"{self.summary_types['detailed']['emoji']} Полное — {self.summary_types['detailed']['desc']}\n\n"
            "<b>⚡ Фишки:</b>\n"
            "🕐 Тайминги для перехода в нужное место\n"
            "📊 Полная информация о видео\n"
            "🎯 Ключевые моменты с временными метками\n\n"
            "💬 <i>Просто отправь ссылку и всё!</i>"
        )
        
        await message.answer(help_text, parse_mode="HTML")
    
    async def show_settings(self, message: types.Message):
        """Show settings menu."""
        user_id = message.from_user.id
        settings = self.get_user_settings(user_id)
        
        current_lang = self.languages[settings['language']]
        current_summary = self.summary_types[settings['summary_type']]
        
        settings_text = (
            "⚙️ <b>Настройки бота</b>\n\n"
            f"🌐 <b>Язык резюме:</b> {current_lang['emoji']} {current_lang['name']}\n"
            f"📋 <b>Тип резюме:</b> {current_summary['emoji']} {current_summary['name']}\n\n"
            "👇 <i>Выбери что хочешь изменить:</i>"
        )
        
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="🌐 Изменить язык", callback_data="change_lang")
        keyboard.button(text="📋 Изменить тип резюме", callback_data="change_summary")
        keyboard.button(text="🔙 Главное меню", callback_data="back_to_menu")
        keyboard.adjust(1)
        
        await message.answer(
            settings_text,
            parse_mode="HTML",
            reply_markup=keyboard.as_markup()
        )
    
    async def callback_settings(self, callback: CallbackQuery):
        """Handle settings callback."""
        await self.show_settings_inline(callback.message, callback.from_user.id)
        await callback.answer()
    
    async def show_settings_inline(self, message: types.Message, user_id: int):
        """Show settings in inline message."""
        settings = self.get_user_settings(user_id)
        
        current_lang = self.languages[settings['language']]
        current_summary = self.summary_types[settings['summary_type']]
        
        settings_text = (
            "⚙️ <b>Настройки бота</b>\n\n"
            f"🌐 <b>Язык резюме:</b> {current_lang['emoji']} {current_lang['name']}\n"
            f"📋 <b>Тип резюме:</b> {current_summary['emoji']} {current_summary['name']}\n\n"
            "👇 <i>Выбери что хочешь изменить:</i>"
        )
        
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="🌐 Изменить язык", callback_data="change_lang")
        keyboard.button(text="📋 Изменить тип резюме", callback_data="change_summary")
        keyboard.button(text="🔙 Главное меню", callback_data="back_to_menu")
        keyboard.adjust(1)
        
        await message.edit_text(
            settings_text,
            parse_mode="HTML",
            reply_markup=keyboard.as_markup()
        )
    
    def is_youtube_url(self, url: str) -> bool:
        """Check if URL is a valid YouTube link."""
        youtube_patterns = [
            r'(?:youtube\.com/watch\?v=)',
            r'(?:youtu\.be/)',
            r'(?:m\.youtube\.com/watch\?v=)',
            r'(?:youtube\.com/embed/)'
        ]
        return any(re.search(pattern, url) for pattern in youtube_patterns)
    
    def extract_video_id(self, url: str) -> Optional[str]:
        """Extract video ID from YouTube URL."""
        patterns = [
            r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]+)',
            r'youtube\.com/watch\?.*v=([a-zA-Z0-9_-]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None
    
    async def handle_youtube_url(self, message: types.Message):
        """Handle YouTube URL messages."""
        url = message.text.strip()
        
        if not self.is_youtube_url(url):
            await message.answer(
                "❌ <b>Это не похоже на ссылку YouTube</b>\n\n"
                "🔗 <b>Поддерживаемые форматы:</b>\n"
                "• youtube.com/watch?v=...\n"
                "• youtu.be/...\n"
                "• m.youtube.com/...\n\n"
                "💡 <i>Попробуй другую ссылку!</i>",
                parse_mode="HTML"
            )
            return
        
        video_id = self.extract_video_id(url)
        if not video_id:
            await message.answer(
                "❌ <b>Не удалось извлечь ID видео</b>\n\n"
                "💡 <i>Проверь корректность ссылки</i>",
                parse_mode="HTML"
            )
            return
        
        user_id = message.from_user.id
        settings = self.get_user_settings(user_id)
        
        # Store URL for processing
        settings['current_url'] = url
        settings['current_video_id'] = video_id
        
        # Extract data and show video info
        await self.extract_and_show_video_info(message, url, user_id)
    
    async def show_video_options(self, message: types.Message, url: str, user_id: int):
        """Show video processing options."""
        settings = self.get_user_settings(user_id)
        
        current_lang = self.languages[settings['language']]
        current_summary = self.summary_types[settings['summary_type']]
        
        options_text = (
            "🎥 <b>YouTube видео найдено!</b>\n\n"
            f"🔗 <b>Ссылка:</b> <code>{url}</code>\n\n"
            f"⚙️ <b>Текущие настройки:</b>\n"
            f"🌐 Язык: {current_lang['emoji']} {current_lang['name']}\n"
            f"📋 Тип: {current_summary['emoji']} {current_summary['name']}\n\n"
            f"👇 <i>Выбери действие:</i>"
        )
        
        keyboard = InlineKeyboardBuilder()
        keyboard.button(
            text=f"🚀 Создать резюме ({current_lang['emoji']} {current_summary['emoji']})", 
            callback_data=f"process_{user_id}"
        )
        keyboard.button(text="⚙️ Изменить настройки", callback_data="settings")
        keyboard.adjust(1)
        
        await message.answer(
            options_text,
            parse_mode="HTML",
            reply_markup=keyboard.as_markup()
        )
    
    async def callback_process_video(self, callback: CallbackQuery):
        """Handle video processing callback."""
        try:
            user_id = callback.from_user.id
            settings = self.get_user_settings(user_id)
            
            url = settings.get('current_url')
            if not url:
                await callback.answer("❌ Ссылка не найдена. Отправь её заново.")
                return
            
            # Start processing
            await self.process_youtube_video(callback.message, url, user_id)
            await callback.answer()
            
        except Exception as e:
            logger.error(f"Error in process callback: {e}")
            await callback.answer("❌ Произошла ошибка при обработке")
    
    async def callback_ai_resume(self, callback: CallbackQuery):
        """Handle AI resume generation callback."""
        try:
            user_id = callback.from_user.id
            settings = self.get_user_settings(user_id)
            
            content = settings.get('current_content')
            url = settings.get('current_url')
            
            if not content or not url:
                await callback.answer("❌ Данные не найдены. Отправь ссылку заново.")
                return
            
            # Generate AI summary
            await self.generate_ai_summary(callback.message, content, url, user_id)
            await callback.answer()
            
        except Exception as e:
            logger.error(f"Error in AI resume callback: {e}")
            await callback.answer("❌ Произошла ошибка при создании резюме")
    
    async def extract_and_show_video_info(self, message: types.Message, url: str, user_id: int):
        """Extract YouTube data and show video info with description."""
        try:
            # Step 1: Show extraction progress
            progress_msg = await message.answer(
                "🔍 <b>Извлекаю данные из YouTube...</b>\n\n"
                "⏳ <i>Получаю информацию о видео...</i>",
                parse_mode="HTML"
            )
            
            # Send typing indicator
            await self.bot.send_chat_action(message.chat.id, 'typing')
            
            # Extract content
            extraction_result = await extract_youtube_content(url)
            
            if not extraction_result or not extraction_result.content:
                error_msg = extraction_result.error_message if extraction_result else "Неизвестная ошибка"
                await progress_msg.edit_text(
                    f"❌ <b>Ошибка извлечения</b>\n\n"
                    f"🔍 <b>Что произошло:</b> {error_msg}\n\n"
                    f"💡 <b>Возможные причины:</b>\n"
                    f"• Видео слишком длинное\n"
                    f"• Нет доступных субтитров\n"
                    f"• Видео заблокировано или удалено\n\n"
                    f"🔄 <i>Попробуй другое видео</i>",
                    parse_mode="HTML"
                )
                return
            
            # Step 2: Show extracted data
            video_info = extraction_result.video_info
            content = extraction_result.content
            
            # Format duration
            duration_mins = video_info.duration // 60
            duration_secs = video_info.duration % 60
            
            # Create beautiful info display with required format
            # Format publish date
            publish_date = video_info.publish_date.strftime('%d.%m.%Y')
            
            # Format view count with spaces
            views_formatted = f"{video_info.view_count:,}".replace(',', ' ')
            
            # Don't use info_text string - build with Text components directly
            
            # Format transcript with timestamps (limited for telegram)
            full_transcript = ""
            transcript_char_limit = 2000  # Safe limit for ExpandableBlockQuote
            current_length = 0
            segments_shown = 0
            total_segments = len(extraction_result.transcript_segments) if extraction_result.transcript_segments else 0
            
            if extraction_result.transcript_segments and len(extraction_result.transcript_segments) > 0:
                for segment in extraction_result.transcript_segments:
                    start_time = int(segment.get('start', 0))
                    mins = start_time // 60
                    secs = start_time % 60
                    text = segment.get('text', '').strip()
                    if text:
                        segment_text = f"[{mins:02d}:{secs:02d}] {text}\n"
                        
                        # Check if adding this segment would exceed limit
                        if current_length + len(segment_text) > transcript_char_limit:
                            remaining = total_segments - segments_shown
                            if remaining > 0:
                                full_transcript += f"\n... и еще {remaining} сегментов с таймингами"
                            break
                            
                        full_transcript += segment_text
                        current_length += len(segment_text)
                        segments_shown += 1
            else:
                # Fallback to truncated simple content
                full_transcript = content[:transcript_char_limit] + ("..." if len(content) > transcript_char_limit else "")
            
            # Get original description and make it expandable like transcript
            from utils.formatters import clean_video_description
            full_description = clean_video_description(video_info.description or "")
            
            # Create expandable description block
            description_expandable = ""
            if full_description and full_description.strip() != "Описание недоступно":
                # Show first 150 chars as preview
                if len(full_description) > 150:
                    description_expandable = f"<blockquote expandable>📖 <b>Описание</b>\n{full_description}</blockquote>"
                else:
                    # Short descriptions don't need to be expandable
                    description_expandable = f"📖 <b>Описание</b>\n{full_description}"
            else:
                description_expandable = "📖 <b>Описание</b>\nОписание недоступно"
            
            # Create expandable content with transcript segments only
            transcript_expandable = ""
            if extraction_result.transcript_segments and len(extraction_result.transcript_segments) > 0:
                transcript_preview = ""
                for i, segment in enumerate(extraction_result.transcript_segments[:20]):  # First 20 segments
                    start_time = int(segment.get('start', 0))
                    mins = start_time // 60
                    secs = start_time % 60
                    text = segment.get('text', '').strip()
                    if text:
                        transcript_preview += f"[{mins:02d}:{secs:02d}] {text}\n"
                
                transcript_expandable = f"<blockquote expandable>📝 НАЧАЛО ВИДЕО:\n{transcript_preview}</blockquote>"
            else:
                transcript_expandable = ""
            
            # Limit video title length too
            title = video_info.title
            if len(title) > 500:  # Увеличил лимит
                title = title[:497] + "..."
            
            info_text = (
                f"🎥 <b>Название:</b> {title}\n"
                f"👤 <b>Канал:</b> {video_info.channel}\n"
                f"📅 <b>Дата:</b> {publish_date}\n"
                f"⏱️ <b>Длительность:</b> {duration_mins:02d}:{duration_secs:02d}\n"
                f"👁️ <b>Просмотры:</b> {views_formatted}\n\n"
                f"{description_expandable}\n\n"
                f"{transcript_expandable}"
            )
            
            # Add AI Resume button
            ai_keyboard = InlineKeyboardBuilder()
            ai_keyboard.button(text="🤖 ИИ Резюме", callback_data=f"ai_resume_{user_id}")
            ai_keyboard.button(text="⚙️ Настройки", callback_data="settings")
            ai_keyboard.adjust(1)

            # Check total message length and send with HTML formatting
            try:
                await progress_msg.edit_text(
                    info_text,
                    parse_mode="HTML",
                    reply_markup=ai_keyboard.as_markup()
                )
            except Exception as e:
                if "text is too long" in str(e).lower():
                    # Fallback to basic info without expandable blocks
                    short_description = full_description[:300] + "..." if len(full_description) > 300 else full_description
                    fallback_text = (
                        f"🎥 <b>Название:</b> {title}\n"
                        f"👤 <b>Канал:</b> {video_info.channel}\n"
                        f"📅 <b>Дата:</b> {publish_date}\n"
                        f"⏱️ <b>Длительность:</b> {duration_mins:02d}:{duration_secs:02d}\n"
                        f"👁️ <b>Просмотры:</b> {views_formatted}\n\n"
                        f"📖 <b>Описание:</b> {short_description}"
                    )
                    await progress_msg.edit_text(
                        fallback_text,
                        parse_mode="HTML",
                        reply_markup=ai_keyboard.as_markup()
                    )
                else:
                    raise
            
            # Store content and video info for AI processing
            settings = self.get_user_settings(user_id)
            settings['current_content'] = content
            settings['current_video_info'] = video_info
            
        except Exception as e:
            logger.error(f"Error extracting video info: {e}")
            error_text = (
                f"❌ <b>Ошибка при извлечении данных</b>\n\n"
                f"🔍 <b>Что произошло:</b> {str(e)}\n\n"
                f"💡 <b>Попробуй:</b>\n"
                f"• Другое видео\n"
                f"• Проверить ссылку\n"
                f"• Повторить попытку\n\n"
                f"🔄 <i>Отправь ссылку заново</i>"
            )
            
            await progress_msg.edit_text(error_text, parse_mode="HTML")
    
    # Missing callback methods
    async def callback_language(self, callback: CallbackQuery):
        """Handle language selection callback."""
        lang_code = callback.data.split('_')[1]
        user_id = callback.from_user.id
        
        settings = self.get_user_settings(user_id)
        settings['language'] = lang_code
        
        lang_info = self.languages[lang_code]
        await callback.answer(f"✅ Язык изменен на {lang_info['name']}")
        
        # Update settings display
        await self.show_settings_inline(callback.message, user_id)
    
    async def callback_summary_type(self, callback: CallbackQuery):
        """Handle summary type selection callback."""
        summary_type = callback.data.split('_')[1]
        user_id = callback.from_user.id
        
        settings = self.get_user_settings(user_id)
        settings['summary_type'] = summary_type
        
        summary_info = self.summary_types[summary_type]
        await callback.answer(f"✅ Тип изменен на {summary_info['name']}")
        
        # Update settings display
        await self.show_settings_inline(callback.message, user_id)
    
    async def callback_change_language(self, callback: CallbackQuery):
        """Show language selection menu."""
        user_id = callback.from_user.id
        settings = self.get_user_settings(user_id)
        current_lang = settings['language']
        
        keyboard = InlineKeyboardBuilder()
        for lang_code, lang_info in self.languages.items():
            is_current = " ✅" if lang_code == current_lang else ""
            keyboard.button(
                text=f"{lang_info['emoji']} {lang_info['name']}{is_current}",
                callback_data=f"lang_{lang_code}"
            )
        keyboard.button(text="🔙 Назад", callback_data="settings")
        keyboard.adjust(1)
        
        await callback.message.edit_text(
            "🌐 <b>Выберите язык для резюме:</b>",
            parse_mode="HTML",
            reply_markup=keyboard.as_markup()
        )
        await callback.answer()
    
    async def callback_change_summary(self, callback: CallbackQuery):
        """Show summary type selection menu."""
        user_id = callback.from_user.id
        settings = self.get_user_settings(user_id)
        current_type = settings['summary_type']
        
        keyboard = InlineKeyboardBuilder()
        for type_code, type_info in self.summary_types.items():
            is_current = " ✅" if type_code == current_type else ""
            keyboard.button(
                text=f"{type_info['emoji']} {type_info['name']} - {type_info['desc']}{is_current}",
                callback_data=f"summary_{type_code}"
            )
        keyboard.button(text="🔙 Назад", callback_data="settings")
        keyboard.adjust(1)
        
        await callback.message.edit_text(
            "📋 <b>Выберите тип резюме:</b>",
            parse_mode="HTML",
            reply_markup=keyboard.as_markup()
        )
        await callback.answer()
    
    async def callback_new_video(self, callback: CallbackQuery):
        """Handle new video request."""
        await callback.message.edit_text(
            "🎥 <b>Отправьте ссылку на новое YouTube видео!</b>\n\n"
            "🔗 <b>Поддерживаемые форматы:</b>\n"
            "• youtube.com/watch?v=...\n"
            "• youtu.be/...\n"
            "• m.youtube.com/...",
            parse_mode="HTML"
        )
        await callback.answer()
    
    async def callback_back_to_menu(self, callback: CallbackQuery):
        """Handle back to main menu."""
        await callback.message.edit_text(
            "🏠 <b>Главное меню</b>\n\n"
            "🎥 Отправьте ссылку на YouTube видео для создания резюме!",
            parse_mode="HTML"
        )
        await callback.answer()
    
    async def generate_ai_summary(self, message: types.Message, content: str, url: str, user_id: int):
        """Generate AI summary for YouTube content using new service."""
        settings = self.get_user_settings(user_id)
        
        try:
            # Convert settings to UserSettings object
            from models.user import UserSettings
            user_settings = UserSettings(
                user_id=user_id,
                language=settings['language'],
                summary_type=settings['summary_type']
            )
            
            # Show progress message using service
            progress_text = self.summarizer_service.get_progress_message(user_settings)
            processing_msg = await message.answer(progress_text, parse_mode="HTML")
            
            # Send typing indicator
            await self.bot.send_chat_action(message.chat.id, 'typing')
            
            # Get video info from user settings for display
            video_info = settings.get('current_video_info')
            
            # Generate summary using service
            summary_result = await self.summarizer_service.generate_summary(
                content=content,
                video_info=video_info,
                user_settings=user_settings,
                user_id=user_id,
                original_url=url
            )
            
            # Format result using service
            formatted_message = self.summarizer_service.format_summary_message(
                summary_result, 
                video_info
            )
            
            # Create "New Video" button
            keyboard = InlineKeyboardBuilder()
            keyboard.button(text="🎥 Новое видео", callback_data="new_video")
            keyboard.button(text="⚙️ Настройки", callback_data="settings")
            keyboard.adjust(2)
            
            await processing_msg.edit_text(
                formatted_message,
                parse_mode="HTML",
                reply_markup=keyboard.as_markup()
            )
            
        except Exception as e:
            logger.error(f"Error generating AI summary: {e}")
            error_text = (
                f"❌ <b>Ошибка при создании резюме</b>\n\n"
                f"🔍 <b>Что произошло:</b> {str(e)}\n\n"
                f"💡 <b>Попробуй:</b>\n"
                f"• Повторить попытку\n"
                f"• Изменить настройки\n"
                f"• Отправить другое видео\n\n"
                f"🔄 <i>Нажми кнопку ещё раз</i>"
            )
            
            await message.answer(error_text, parse_mode="HTML")
    
    async def handle_text_message(self, message: types.Message):
        """Handle regular text messages."""
        if self.is_youtube_url(message.text):
            await self.handle_youtube_url(message)
        else:
            await message.answer(
                "🎥 <b>Отправь ссылку на YouTube видео!</b>\n\n"
                "🔗 <b>Поддерживаемые форматы:</b>\n"
                "• youtube.com/watch?v=...\n"
                "• youtu.be/...\n"
                "• m.youtube.com/...\n\n"
                "💡 <i>Или используй меню для навигации</i>",
                parse_mode="HTML"
            )
    
    async def start_bot(self):
        """Start the bot."""
        logger.info("Starting YouTubeSamBot...")
        try:
            await self.dp.start_polling(self.bot)
        except Exception as e:
            logger.error(f"Error starting bot: {e}")
        finally:
            await self.bot.session.close()

async def main():
    """Main function to run the bot."""
    bot = YouTubeSamBot()
    await bot.start_bot()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot crashed: {e}")