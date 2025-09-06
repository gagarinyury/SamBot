"""
SamBot - Intelligent Multilingual Telegram Summarizer Bot
Main bot application with URL processing and user management.
"""

import asyncio
import logging
import re
from typing import Dict, List, Optional
from urllib.parse import urlparse

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from telegram.error import TelegramError

from config import get_config
from database.manager import get_database_manager
from extractors.youtube import extract_youtube_content
from extractors.web import extract_web_content
from summarizers.deepseek import summarize_content

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class SamBot:
    """
    Main SamBot class handling all Telegram interactions.
    Integrates content extraction and AI summarization.
    """
    
    def __init__(self):
        self.config = get_config()
        self.db = get_database_manager()
        
        # Bot configuration
        self.bot_config = {
            'max_message_length': 4096,  # Telegram limit
            'progress_update_interval': 2,  # seconds
            'supported_languages': ['fr', 'en', 'ru'],
            'default_language': 'fr',  # France market
        }
        
        logger.info("SamBot initialized successfully")
    
    async def initialize(self):
        """Initialize database and validate configuration."""
        try:
            await self.db.initialize()
            self.config.validate()
            logger.info("SamBot initialization complete")
        except Exception as e:
            logger.error(f"SamBot initialization failed: {e}")
            raise
    
    # ========================================
    # COMMAND HANDLERS
    # ========================================
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command - welcome new users."""
        user = update.effective_user
        chat_id = update.effective_chat.id
        
        try:
            # Create or get user from database
            user_data = await self.db.get_or_create_user(
                telegram_id=user.id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name,
                language_code=user.language_code or 'fr'
            )
            
            # Log registration event for analytics
            await self.db.log_event(
                event_type='user_started',
                user_id=user_data['id'],
                data={'telegram_username': user.username, 'language': user.language_code}
            )
            
            # Get localized welcome message
            language = user_data.get('language_code', 'fr')
            welcome_msg = await self.db.get_translation('welcome_message', language)
            
            if not welcome_msg:
                # Fallback to default French message
                welcome_msg = ("🎉 Bienvenue sur SamBot !\\n\\n"
                              "Je suis votre assistant IA pour créer des résumés intelligents "
                              "de vidéos YouTube et d'articles web.\\n\\n"
                              "🔗 Envoyez-moi simplement un lien et je vous ferai un résumé !")
            
            await update.message.reply_text(welcome_msg, parse_mode='Markdown')
            
            logger.info(f"User {user.id} started bot")
            
        except Exception as e:
            logger.error(f"Start command failed for user {user.id}: {e}")
            await update.message.reply_text(
                "❌ Désolé, une erreur s'est produite. Veuillez réessayer."
            )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command - show usage instructions."""
        user = update.effective_user
        
        try:
            # Get user language preference
            user_data = await self.db.get_or_create_user(telegram_id=user.id)
            language = user_data.get('language_code', 'fr')
            
            # Get localized help message
            help_msg = await self.db.get_translation('help_message', language)
            
            if not help_msg:
                # Fallback to default French help
                help_msg = ("📖 *Aide SamBot*\\n\\n"
                           "🔗 Envoyez un lien YouTube ou d'article web\\n"
                           "📝 Recevez un résumé intelligent\\n"
                           "⚙️ /settings - Paramètres\\n"
                           "💎 /upgrade - Plans premium\\n\\n"
                           "*Langues supportées :* Français, English, Русский")
            
            await update.message.reply_text(help_msg, parse_mode='Markdown')
            
            # Log help request
            await self.db.log_event(
                event_type='help_requested',
                user_id=user_data['id'],
                data={'language': language}
            )
            
        except Exception as e:
            logger.error(f"Help command failed for user {user.id}: {e}")
            await update.message.reply_text(
                "❌ Désolé, une erreur s'est produite. Veuillez réessayer."
            )
    
    async def settings_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /settings command - user preferences."""
        user = update.effective_user
        
        try:
            user_data = await self.db.get_or_create_user(telegram_id=user.id)
            language = user_data.get('language_code', 'fr')
            
            # Create settings keyboard
            keyboard = [
                [
                    InlineKeyboardButton("🌍 Français", callback_data="lang_fr"),
                    InlineKeyboardButton("🇬🇧 English", callback_data="lang_en"),
                    InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru")
                ],
                [
                    InlineKeyboardButton("📄 Bref", callback_data="length_brief"),
                    InlineKeyboardButton("⚙️ Moyen", callback_data="length_medium"),
                    InlineKeyboardButton("📝 Détaillé", callback_data="length_detailed")
                ],
                [
                    InlineKeyboardButton("📊 Statistiques", callback_data="show_stats"),
                    InlineKeyboardButton("❌ Fermer", callback_data="close_menu")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            settings_text = f"""
⚙️ *Paramètres SamBot*

📱 *Langue actuelle:* {language.upper()}
📝 *Longueur des résumés:* Moyen
📈 *Plan:* {user_data.get('subscription_type', 'free').title()}

Utilisez les boutons ci-dessous pour modifier vos préférences:
            """
            
            await update.message.reply_text(
                settings_text, 
                reply_markup=reply_markup, 
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Settings command failed for user {user.id}: {e}")
            await update.message.reply_text(
                "❌ Impossible d'ouvrir les paramètres. Réessayez plus tard."
            )
    
    async def upgrade_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /upgrade command - subscription plans."""
        user = update.effective_user
        
        try:
            user_data = await self.db.get_or_create_user(telegram_id=user.id)
            language = user_data.get('language_code', 'fr')
            current_plan = user_data.get('subscription_type', 'free')
            
            # Get plan names and descriptions in user's language
            free_name = await self.db.get_translation('plan_free_name', language) or "🆓 Gratuit"
            premium_name = await self.db.get_translation('plan_premium_name', language) or "💎 Premium"
            vip_name = await self.db.get_translation('plan_vip_name', language) or "👑 VIP"
            
            free_desc = await self.db.get_translation('plan_free_desc', language) or "5 résumés par jour"
            premium_desc = await self.db.get_translation('plan_premium_desc', language) or "50 résumés par jour"
            vip_desc = await self.db.get_translation('plan_vip_desc', language) or "Résumés illimités"
            
            # Create upgrade keyboard
            keyboard = []
            
            # Free plan (always show current status)
            free_btn_text = f"{free_name} {'✅' if current_plan == 'free' else ''}"
            keyboard.append([InlineKeyboardButton(free_btn_text, callback_data="plan_free")])
            
            # Premium plan
            premium_btn_text = f"{premium_name} 9.99€ {'✅' if current_plan == 'premium' else '💳'}"
            keyboard.append([InlineKeyboardButton(premium_btn_text, callback_data="plan_premium")])
            
            # VIP plan  
            vip_btn_text = f"{vip_name} 29.99€ {'✅' if current_plan == 'vip' else '💳'}"
            keyboard.append([InlineKeyboardButton(vip_btn_text, callback_data="plan_vip")])
            
            keyboard.append([InlineKeyboardButton("❌ Fermer", callback_data="close_menu")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            upgrade_text = f"""
💎 *Plans d'abonnement SamBot*

{free_name}
• {free_desc}
• Support communautaire

{premium_name} - 9.99€/mois
• {premium_desc}
• Support prioritaire
• Résumés détaillés

{vip_name} - 29.99€/mois  
• {vip_desc}
• Prompts personnalisés
• Accès API
• Support téléphonique

*Plan actuel:* {current_plan.title()}
            """
            
            await update.message.reply_text(
                upgrade_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Upgrade command failed for user {user.id}: {e}")
            await update.message.reply_text(
                "❌ Impossible d'afficher les plans. Réessayez plus tard."
            )
    
    # ========================================
    # URL VALIDATION HELPERS
    # ========================================
    
    def extract_url_from_message(self, text: str) -> Optional[str]:
        """Extract URL from message text."""
        # Look for URLs in the message
        url_pattern = re.compile(
            r'https?://(?:[-\w.])+(?:[:\d]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:#(?:[\w.])*)?)?'
        )
        
        urls = url_pattern.findall(text)
        return urls[0] if urls else None
    
    def is_youtube_url(self, url: str) -> bool:
        """Check if URL is a YouTube URL."""
        if not url:
            return False
            
        parsed = urlparse(url)
        return parsed.netloc.lower() in [
            'youtube.com', 'www.youtube.com', 'youtu.be', 'm.youtube.com'
        ]
    
    def is_web_url(self, url: str) -> bool:
        """Check if URL is a valid web URL (not YouTube)."""
        if not url:
            return False
            
        try:
            parsed = urlparse(url)
            return parsed.scheme in ['http', 'https'] and not self.is_youtube_url(url)
        except Exception:
            return False
    
    # ========================================
    # MESSAGE HANDLER (URL PROCESSING)
    # ========================================
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle all text messages - primarily URL processing."""
        user = update.effective_user
        message_text = update.message.text
        
        try:
            # Extract URL from message
            url = self.extract_url_from_message(message_text)
            
            if not url:
                # No URL found, send help message
                await update.message.reply_text(
                    "🔗 Envoyez-moi un lien YouTube ou d'article web pour obtenir un résumé intelligent !\\n\\n"
                    "Tapez /help pour plus d'informations."
                )
                return
            
            # Get user data
            user_data = await self.db.get_or_create_user(telegram_id=user.id)
            
            # Check user limits before processing
            limits = await self.db.check_user_limits(user_data['id'])
            if not limits['allowed']:
                error_msg = await self.db.get_translation('error_limit_reached', user_data.get('language_code', 'fr'))
                if not error_msg:
                    error_msg = "⚠️ Limite quotidienne atteinte !\\n\\n🆓 Gratuit : 5 résumés/jour\\n💎 Premium : 50 résumés/jour\\n👑 VIP : Illimité\\n\\n/upgrade pour plus de résumés"
                
                await update.message.reply_text(error_msg)
                return
            
            # Determine content type and process URL
            if self.is_youtube_url(url):
                await self.process_youtube_url(update, user_data, url)
            elif self.is_web_url(url):
                await self.process_web_url(update, user_data, url)
            else:
                # Invalid URL
                error_msg = await self.db.get_translation('error_invalid_url', user_data.get('language_code', 'fr'))
                if not error_msg:
                    error_msg = "❌ URL non valide\\n\\nVeuillez envoyer un lien YouTube ou d'article web valide."
                
                await update.message.reply_text(error_msg)
                
        except Exception as e:
            logger.error(f"Message handling failed for user {user.id}: {e}")
            await update.message.reply_text(
                "❌ Une erreur inattendue s'est produite. Veuillez réessayer."
            )
    
    async def process_youtube_url(self, update: Update, user_data: Dict, url: str):
        """Process YouTube URL - extract and summarize."""
        language = user_data.get('language_code', 'fr')
        user_id = user_data['id']
        
        # Send initial progress message
        progress_msg = await update.message.reply_text(
            "🎥 *YouTube vidéo détectée*\\n\\n⏳ Extraction des sous-titres...", 
            parse_mode='Markdown'
        )
        
        try:
            # Extract YouTube content
            extraction_result = await extract_youtube_content(
                url=url,
                preferred_languages=[language, 'en', 'fr'],  # User lang + fallbacks
                allow_auto_generated=True,
                user_id=user_id
            )
            
            # Check extraction status
            if extraction_result.status.value != 'success':
                await self.handle_extraction_error(update, progress_msg, extraction_result, language)
                return
            
            # Update progress
            await progress_msg.edit_text(
                "🎥 *YouTube vidéo détectée*\\n\\n✅ Sous-titres extraits\\n🤖 Génération du résumé...", 
                parse_mode='Markdown'
            )
            
            # Get user's preferred summary length
            summary_length = user_data.get('summary_length', 'medium')  # Default medium
            
            # Summarize content
            summary_result = await summarize_content(
                content=extraction_result.content,
                content_type='youtube',
                target_language=language,
                summary_length=summary_length,
                user_id=user_id,
                original_url=url
            )
            
            # Record usage in database
            await self.db.record_usage(user_id, summary_result.tokens_used)
            
            # Log successful processing
            await self.db.log_event(
                event_type='youtube_summarized',
                user_id=user_id,
                data={
                    'url': url,
                    'video_title': extraction_result.video_info.title if extraction_result.video_info else 'Unknown',
                    'tokens_used': summary_result.tokens_used,
                    'cached': summary_result.cached,
                    'language': language,
                    'summary_length': summary_length
                }
            )
            
            # Format and send result
            await self.send_summary_result(update, progress_msg, extraction_result, summary_result)
            
        except Exception as e:
            logger.error(f"YouTube processing failed for user {user_data['telegram_id']}: {e}")
            await progress_msg.edit_text(
                "❌ *Erreur de traitement*\\n\\nUne erreur inattendue s'est produite lors du traitement de la vidéo. Veuillez réessayer.",
                parse_mode='Markdown'
            )
    
    async def process_web_url(self, update: Update, user_data: Dict, url: str):
        """Process web URL - extract and summarize."""
        language = user_data.get('language_code', 'fr')
        user_id = user_data['id']
        
        # Send initial progress message
        progress_msg = await update.message.reply_text(
            "🌐 *Article web détecté*\\n\\n⏳ Extraction du contenu...", 
            parse_mode='Markdown'
        )
        
        try:
            # Extract web content
            extraction_result = await extract_web_content(
                url=url,
                preferred_languages=[language, 'en', 'fr'],  # User lang + fallbacks
                max_content_length=50000,  # 50KB limit for processing
                user_id=user_id,
                follow_redirects=True,
                respect_robots=True
            )
            
            # Check extraction status
            if extraction_result.status.value != 'success':
                await self.handle_extraction_error(update, progress_msg, extraction_result, language)
                return
            
            # Update progress
            await progress_msg.edit_text(
                "🌐 *Article web détecté*\\n\\n✅ Contenu extrait\\n🤖 Génération du résumé...", 
                parse_mode='Markdown'
            )
            
            # Get user's preferred summary length
            summary_length = user_data.get('summary_length', 'medium')  # Default medium
            
            # Summarize content
            summary_result = await summarize_content(
                content=extraction_result.content,
                content_type='web',
                target_language=language,
                summary_length=summary_length,
                user_id=user_id,
                original_url=url
            )
            
            # Record usage in database
            await self.db.record_usage(user_id, summary_result.tokens_used)
            
            # Log successful processing
            await self.db.log_event(
                event_type='web_summarized',
                user_id=user_id,
                data={
                    'url': url,
                    'final_url': extraction_result.final_url,
                    'article_title': extraction_result.article_info.title if extraction_result.article_info else 'Unknown',
                    'tokens_used': summary_result.tokens_used,
                    'cached': summary_result.cached,
                    'language': language,
                    'summary_length': summary_length,
                    'extraction_method': extraction_result.extraction_method.value
                }
            )
            
            # Format and send result
            await self.send_summary_result(update, progress_msg, extraction_result, summary_result)
            
        except Exception as e:
            logger.error(f"Web processing failed for user {user_data['telegram_id']}: {e}")
            await progress_msg.edit_text(
                "❌ *Erreur de traitement*\\n\\nUne erreur inattendue s'est produite lors du traitement de l'article. Veuillez réessayer.",
                parse_mode='Markdown'
            )
    
    # ========================================
    # RESULT FORMATTING AND ERROR HANDLING  
    # ========================================
    
    async def handle_extraction_error(self, update: Update, progress_msg, extraction_result, language: str):
        """Handle extraction errors with appropriate user messages."""
        status = extraction_result.status.value
        error_msg = extraction_result.error_message
        
        # Map extraction errors to user-friendly messages
        error_messages = {
            'no_transcript': {
                'fr': "❌ *Pas de sous-titres disponibles*\\n\\nCette vidéo YouTube n'a pas de sous-titres dans les langues supportées. Essayez une autre vidéo.",
                'en': "❌ *No subtitles available*\\n\\nThis YouTube video doesn't have subtitles in supported languages. Try another video.",
                'ru': "❌ *Субтитры недоступны*\\n\\nУ этого YouTube видео нет субтитров на поддерживаемых языках. Попробуйте другое видео."
            },
            'video_unavailable': {
                'fr': "❌ *Vidéo non disponible*\\n\\nCette vidéo YouTube n'est pas accessible. Elle pourrait être privée ou supprimée.",
                'en': "❌ *Video unavailable*\\n\\nThis YouTube video is not accessible. It might be private or deleted.",
                'ru': "❌ *Видео недоступно*\\n\\nЭто YouTube видео недоступно. Возможно, оно приватное или удалено."
            },
            'private_video': {
                'fr': "❌ *Vidéo privée*\\n\\nCette vidéo YouTube est privée et ne peut pas être traitée.",
                'en': "❌ *Private video*\\n\\nThis YouTube video is private and cannot be processed.",
                'ru': "❌ *Приватное видео*\\n\\nЭто YouTube видео приватное и не может быть обработано."
            },
            'duration_exceeded': {
                'fr': "⏱️ *Vidéo trop longue*\\n\\nCette vidéo dépasse la limite de 2 heures. Essayez des vidéos plus courtes.",
                'en': "⏱️ *Video too long*\\n\\nThis video exceeds the 2-hour limit. Try shorter videos.",
                'ru': "⏱️ *Слишком длинное видео*\\n\\nЭто видео превышает лимит в 2 часа. Попробуйте более короткие видео."
            },
            'invalid_url': {
                'fr': "❌ *URL invalide*\\n\\nL'URL fournie n'est pas valide. Vérifiez et réessayez.",
                'en': "❌ *Invalid URL*\\n\\nThe provided URL is not valid. Please check and try again.",
                'ru': "❌ *Неверная ссылка*\\n\\nПредоставленная ссылка недействительна. Проверьте и попробуйте снова."
            },
            'no_content': {
                'fr': "📄 *Pas de contenu*\\n\\nImpossible d'extraire le contenu de cette page. Essayez une autre URL.",
                'en': "📄 *No content*\\n\\nUnable to extract content from this page. Try another URL.",
                'ru': "📄 *Нет контента*\\n\\nНе удалось извлечь контент с этой страницы. Попробуйте другую ссылку."
            },
            'access_denied': {
                'fr': "🚫 *Accès refusé*\\n\\nImpossible d'accéder à cette page. Elle pourrait être protégée.",
                'en': "🚫 *Access denied*\\n\\nUnable to access this page. It might be protected.",
                'ru': "🚫 *Доступ запрещен*\\n\\nНе удалось получить доступ к этой странице. Возможно, она защищена."
            },
            'robots_blocked': {
                'fr': "🤖 *Bloqué par robots.txt*\\n\\nCe site ne permet pas l'extraction automatique de contenu.",
                'en': "🤖 *Blocked by robots.txt*\\n\\nThis site doesn't allow automatic content extraction.",
                'ru': "🤖 *Заблокировано robots.txt*\\n\\nЭтот сайт не разрешает автоматическое извлечение контента."
            },
            'timeout': {
                'fr': "⏲️ *Délai dépassé*\\n\\nLe chargement de la page a pris trop de temps. Réessayez plus tard.",
                'en': "⏲️ *Timeout*\\n\\nPage loading took too long. Try again later.",
                'ru': "⏲️ *Превышено время ожидания*\\n\\nЗагрузка страницы заняла слишком много времени. Попробуйте позже."
            }
        }
        
        # Get appropriate error message
        user_message = error_messages.get(status, {}).get(language)
        if not user_message:
            # Fallback to generic error message
            user_message = f"❌ *Erreur*\\n\\n{error_msg or 'Une erreur est survenue lors du traitement.'}"
        
        await progress_msg.edit_text(user_message, parse_mode='Markdown')
    
    async def send_summary_result(self, update: Update, progress_msg, extraction_result, summary_result):
        """Format and send the summary result to user."""
        try:
            # Prepare result message components
            summary_text = summary_result.summary
            cached_indicator = " ⚡" if summary_result.cached else ""
            
            # Get content metadata
            if hasattr(extraction_result, 'video_info') and extraction_result.video_info:
                # YouTube video
                title = extraction_result.video_info.title[:100] + "..." if len(extraction_result.video_info.title) > 100 else extraction_result.video_info.title
                channel = extraction_result.video_info.channel
                duration_minutes = extraction_result.video_info.duration // 60
                
                header = f"🎥 **{title}**\\n📺 {channel} • ⏱️ {duration_minutes}min{cached_indicator}\\n\\n"
                
            elif hasattr(extraction_result, 'article_info') and extraction_result.article_info:
                # Web article
                title = extraction_result.article_info.title[:100] + "..." if len(extraction_result.article_info.title) > 100 else extraction_result.article_info.title
                domain = extraction_result.article_info.domain or "Web"
                
                header = f"🌐 **{title}**\\n📰 {domain}{cached_indicator}\\n\\n"
                
            else:
                # Fallback
                header = f"📄 **Résumé**{cached_indicator}\\n\\n"
            
            # Prepare full message
            full_message = header + summary_text
            
            # Check message length (Telegram limit is 4096)
            if len(full_message) > self.bot_config['max_message_length']:
                # Truncate summary if too long
                max_summary_length = self.bot_config['max_message_length'] - len(header) - 50  # Leave room for "..."
                truncated_summary = summary_text[:max_summary_length] + "\\n\\n*[Résumé tronqué]*"
                full_message = header + truncated_summary
            
            # Add footer with stats
            footer = f"\\n\\n📊 *{summary_result.tokens_used} tokens • {summary_result.processing_time:.1f}s*"
            
            # Final check for length
            if len(full_message + footer) <= self.bot_config['max_message_length']:
                full_message += footer
            
            # Send result
            await progress_msg.edit_text(full_message, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Failed to send summary result: {e}")
            await progress_msg.edit_text(
                f"✅ *Résumé généré*\\n\\n{summary_result.summary[:3000]}",
                parse_mode='Markdown'
            )
    
    # ========================================
    # CALLBACK QUERY HANDLERS (INLINE KEYBOARDS)
    # ========================================
    
    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle all inline keyboard button presses."""
        query = update.callback_query
        user = query.from_user
        data = query.data
        
        try:
            # Acknowledge the callback query
            await query.answer()
            
            # Get user data
            user_data = await self.db.get_or_create_user(telegram_id=user.id)
            
            # Route to appropriate handler
            if data.startswith('lang_'):
                await self.handle_language_change(query, user_data, data)
            elif data.startswith('length_'):
                await self.handle_length_change(query, user_data, data)
            elif data == 'show_stats':
                await self.handle_show_stats(query, user_data)
            elif data.startswith('plan_'):
                await self.handle_plan_selection(query, user_data, data)
            elif data == 'close_menu':
                await self.handle_close_menu(query)
            else:
                await query.answer("❓ Action non reconnue", show_alert=True)
                
        except Exception as e:
            logger.error(f"Callback query handling failed for user {user.id}: {e}")
            await query.answer("❌ Une erreur s'est produite", show_alert=True)
    
    async def handle_language_change(self, query, user_data: Dict, data: str):
        """Handle language selection."""
        language_map = {
            'lang_fr': 'fr',
            'lang_en': 'en', 
            'lang_ru': 'ru'
        }
        
        new_language = language_map.get(data)
        if not new_language:
            await query.answer("❌ Langue invalide", show_alert=True)
            return
        
        try:
            # Update user language in database
            import aiosqlite
            async with aiosqlite.connect(self.db.db_path) as db:
                await db.execute(
                    "UPDATE users SET language_code = ? WHERE telegram_id = ?",
                    (new_language, user_data['telegram_id'])
                )
                await db.commit()
            
            # Get confirmation message in new language
            confirmations = {
                'fr': f"✅ Langue changée en Français",
                'en': f"✅ Language changed to English",  
                'ru': f"✅ Язык изменен на Русский"
            }
            
            await query.answer(confirmations[new_language], show_alert=False)
            
            # Update the settings menu with new language
            await self.refresh_settings_menu(query, user_data, new_language)
            
        except Exception as e:
            logger.error(f"Failed to change language: {e}")
            await query.answer("❌ Impossible de changer la langue", show_alert=True)
    
    async def handle_length_change(self, query, user_data: Dict, data: str):
        """Handle summary length selection."""
        length_map = {
            'length_brief': 'brief',
            'length_medium': 'medium',
            'length_detailed': 'detailed'
        }
        
        new_length = length_map.get(data)
        if not new_length:
            await query.answer("❌ Longueur invalide", show_alert=True)
            return
        
        try:
            # Update user settings in database
            import aiosqlite
            async with aiosqlite.connect(self.db.db_path) as db:
                # First check if user_settings exists
                cursor = await db.execute(
                    "SELECT user_id FROM user_settings WHERE user_id = ?", 
                    (user_data['id'],)
                )
                exists = await cursor.fetchone()
                
                if exists:
                    await db.execute(
                        "UPDATE user_settings SET summary_length = ? WHERE user_id = ?",
                        (new_length, user_data['id'])
                    )
                else:
                    await db.execute(
                        "INSERT INTO user_settings (user_id, summary_length) VALUES (?, ?)",
                        (user_data['id'], new_length)
                    )
                
                await db.commit()
            
            # Confirmation message
            length_names = {
                'brief': 'Bref',
                'medium': 'Moyen', 
                'detailed': 'Détaillé'
            }
            
            await query.answer(f"✅ Longueur: {length_names[new_length]}", show_alert=False)
            
            # Refresh settings menu
            await self.refresh_settings_menu(query, user_data, user_data.get('language_code', 'fr'))
            
        except Exception as e:
            logger.error(f"Failed to change summary length: {e}")
            await query.answer("❌ Impossible de changer la longueur", show_alert=True)
    
    async def handle_show_stats(self, query, user_data: Dict):
        """Show user statistics."""
        try:
            language = user_data.get('language_code', 'fr')
            
            # Get user statistics
            limits = await self.db.check_user_limits(user_data['id'])
            plan = user_data.get('subscription_type', 'free')
            
            # Get usage today
            import aiosqlite
            async with aiosqlite.connect(self.db.db_path) as db:
                cursor = await db.execute(
                    "SELECT requests_count, tokens_used FROM usage_stats WHERE user_id = ? AND date = DATE('now')",
                    (user_data['id'],)
                )
                today_stats = await cursor.fetchone()
            
            requests_today = today_stats[0] if today_stats else 0
            tokens_today = today_stats[1] if today_stats else 0
            
            # Get total usage
            total_requests = user_data.get('total_requests', 0)
            
            stats_text = f"""
📊 *Vos Statistiques*

📅 *Aujourd'hui:*
• Résumés: {requests_today}
• Tokens utilisés: {tokens_today:,}

📈 *Total:*  
• Résumés créés: {total_requests:,}
• Plan actuel: {plan.title()}

💡 *Limites:*
• Restant aujourd'hui: {limits.get('requests_remaining', 0)}
            """
            
            await query.message.reply_text(stats_text.strip(), parse_mode='Markdown')
            await query.answer("📊 Statistiques affichées")
            
        except Exception as e:
            logger.error(f"Failed to show stats: {e}")
            await query.answer("❌ Impossible d'afficher les statistiques", show_alert=True)
    
    async def handle_plan_selection(self, query, user_data: Dict, data: str):
        """Handle subscription plan selection.""" 
        plan_map = {
            'plan_free': 'free',
            'plan_premium': 'premium',
            'plan_vip': 'vip'
        }
        
        selected_plan = plan_map.get(data)
        current_plan = user_data.get('subscription_type', 'free')
        
        if selected_plan == current_plan:
            await query.answer("✅ C'est votre plan actuel", show_alert=False)
            return
        
        if selected_plan == 'free':
            await query.answer("ℹ️ Plan gratuit toujours disponible", show_alert=False)
            return
        
        # For premium/VIP plans, show payment info (placeholder for now)
        plan_prices = {'premium': '9.99€', 'vip': '29.99€'}
        plan_names = {'premium': 'Premium', 'vip': 'VIP'}
        
        payment_info = f"""
💳 *Paiement {plan_names[selected_plan]}*

Prix: {plan_prices[selected_plan]}/mois
        
Pour activer ce plan, contactez le support ou utilisez notre site web.

🌐 sambot-ai.com/upgrade
        """
        
        await query.message.reply_text(payment_info.strip(), parse_mode='Markdown')
        await query.answer(f"💳 Info paiement {plan_names[selected_plan]}")
    
    async def handle_close_menu(self, query):
        """Close the inline keyboard menu."""
        try:
            await query.message.delete()
            await query.answer("❌ Menu fermé")
        except Exception as e:
            # If can't delete (too old message), just remove keyboard
            await query.message.edit_reply_markup(reply_markup=None)
            await query.answer("❌ Menu fermé")
    
    async def refresh_settings_menu(self, query, user_data: Dict, language: str):
        """Refresh the settings menu with updated values."""
        try:
            # Create updated settings keyboard  
            keyboard = [
                [
                    InlineKeyboardButton(f"🌍 {'✅' if language=='fr' else ''} Français", callback_data="lang_fr"),
                    InlineKeyboardButton(f"🇬🇧 {'✅' if language=='en' else ''} English", callback_data="lang_en"),
                    InlineKeyboardButton(f"🇷🇺 {'✅' if language=='ru' else ''} Русский", callback_data="lang_ru")
                ],
                [
                    InlineKeyboardButton("📄 Bref", callback_data="length_brief"),
                    InlineKeyboardButton("⚙️ Moyen", callback_data="length_medium"),
                    InlineKeyboardButton("📝 Détaillé", callback_data="length_detailed")
                ],
                [
                    InlineKeyboardButton("📊 Statistiques", callback_data="show_stats"),
                    InlineKeyboardButton("❌ Fermer", callback_data="close_menu")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            settings_text = f"""
⚙️ *Paramètres SamBot*

📱 *Langue actuelle:* {language.upper()}
📝 *Longueur des résumés:* Moyen  
📈 *Plan:* {user_data.get('subscription_type', 'free').title()}

Utilisez les boutons ci-dessous pour modifier vos préférences:
            """
            
            await query.message.edit_text(
                settings_text.strip(),
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Failed to refresh settings menu: {e}")

def main():
    """Main function to run the bot."""
    try:
        # Initialize bot
        bot = SamBot()
        
        # Create Telegram application
        application = Application.builder().token(bot.config.telegram.bot_token).build()
        
        # Add command handlers
        application.add_handler(CommandHandler("start", bot.start_command))
        application.add_handler(CommandHandler("help", bot.help_command))
        application.add_handler(CommandHandler("settings", bot.settings_command))
        application.add_handler(CommandHandler("upgrade", bot.upgrade_command))
        
        # Add message handler for URL processing
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_message))
        
        # Add callback query handler for inline keyboards
        application.add_handler(CallbackQueryHandler(bot.handle_callback_query))
        
        logger.info("Starting SamBot...")
        
        # Initialize database and run bot in single async context
        async def init_and_run():
            await bot.initialize()
            await application.run_polling()
        
        # Run everything in one event loop
        asyncio.run(init_and_run())
        
    except Exception as e:
        logger.error(f"Bot startup failed: {e}")
        raise

if __name__ == '__main__':
    main()