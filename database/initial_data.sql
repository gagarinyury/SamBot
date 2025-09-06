-- ========================================
-- SamBot Initial Data
-- France market with EUR pricing
-- Multi-language support (FR/RU/EN)
-- ========================================

-- ========================================
-- SUPPORTED LANGUAGES
-- ========================================

INSERT INTO supported_languages (code, name_english, name_native, is_active, is_default, flag_emoji, sort_order) VALUES
('fr', 'French', 'Français', true, true, '🇫🇷', 1),
('en', 'English', 'English', true, false, '🇬🇧', 2),
('ru', 'Russian', 'Русский', true, false, '🇷🇺', 3);

-- ========================================
-- SUBSCRIPTION PLANS (EUR PRICING)
-- ========================================

INSERT INTO subscription_plans (name_key, price_eur_cents, price_usd_cents, price_rub_cents, duration_days, daily_requests_limit, features, is_active, sort_order) VALUES
-- FREE Plan
('plan_free', 0, 0, 0, 365, 5, '["basic_summaries"]', true, 1),

-- PREMIUM Plan (9.99 EUR/month)
('plan_premium', 999, 1099, 99900, 30, 50, '["priority_support", "detailed_summaries", "multiple_lengths", "email_support"]', true, 2),

-- VIP Plan (29.99 EUR/month)
('plan_vip', 2999, 3299, 299900, 30, 999999, '["priority_support", "detailed_summaries", "multiple_lengths", "custom_prompts", "api_access", "white_label", "phone_support"]', true, 3),

-- PREMIUM YEARLY (99.99 EUR/year - 2 months free)
('plan_premium_yearly', 9999, 10999, 999900, 365, 50, '["priority_support", "detailed_summaries", "multiple_lengths", "email_support", "yearly_discount"]', true, 4),

-- VIP YEARLY (299.99 EUR/year - 2 months free)
('plan_vip_yearly', 29999, 32999, 2999900, 365, 999999, '["priority_support", "detailed_summaries", "multiple_lengths", "custom_prompts", "api_access", "white_label", "phone_support", "yearly_discount"]', true, 5);

-- ========================================
-- DEFAULT PROMPT TEMPLATES
-- ========================================

-- French prompts
INSERT INTO prompt_templates (name, content_type, language, template, is_active, is_default, version) VALUES
-- YouTube prompts in French
('youtube_brief_fr', 'youtube', 'fr', 'Créez un résumé bref (2-3 phrases) de cette vidéo YouTube en français :\n\n{content}\n\nRésumé :', true, false, 1),
('youtube_detailed_fr', 'youtube', 'fr', 'Analysez cette transcription YouTube et créez un résumé détaillé en français avec les points clés, les insights principaux, et les conclusions importantes :\n\n{content}\n\nRésumé détaillé :', true, true, 1),

-- Web article prompts in French  
('web_brief_fr', 'web', 'fr', 'Résumez cet article web en 2-3 phrases principales en français :\n\n{content}\n\nRésumé :', true, false, 1),
('web_detailed_fr', 'web', 'fr', 'Analysez cet article et fournissez un résumé détaillé en français avec les points principaux, les arguments clés, et les conclusions :\n\n{content}\n\nRésumé détaillé :', true, true, 1);

-- English prompts
INSERT INTO prompt_templates (name, content_type, language, template, is_active, is_default, version) VALUES
-- YouTube prompts in English
('youtube_brief_en', 'youtube', 'en', 'Create a brief summary (2-3 sentences) of this YouTube video in English:\n\n{content}\n\nSummary:', true, false, 1),
('youtube_detailed_en', 'youtube', 'en', 'Analyze this YouTube transcript and create a detailed summary in English with key points, main insights, and important conclusions:\n\n{content}\n\nDetailed summary:', true, true, 1),

-- Web article prompts in English
('web_brief_en', 'web', 'en', 'Summarize this web article in 2-3 main sentences in English:\n\n{content}\n\nSummary:', true, false, 1),
('web_detailed_en', 'web', 'en', 'Analyze this article and provide a detailed summary in English with main points, key arguments, and conclusions:\n\n{content}\n\nDetailed summary:', true, true, 1);

-- Russian prompts
INSERT INTO prompt_templates (name, content_type, language, template, is_active, is_default, version) VALUES
-- YouTube prompts in Russian
('youtube_brief_ru', 'youtube', 'ru', 'Создайте краткое резюме (2-3 предложения) этого YouTube видео на русском языке:\n\n{content}\n\nКраткое резюме:', true, false, 1),
('youtube_detailed_ru', 'youtube', 'ru', 'Проанализируйте эту расшифровку YouTube и создайте подробное резюме на русском языке с ключевыми моментами, основными выводами и важными заключениями:\n\n{content}\n\nПодробное резюме:', true, true, 1),

-- Web article prompts in Russian
('web_brief_ru', 'web', 'ru', 'Резюмируйте эту веб-статью в 2-3 основных предложениях на русском языке:\n\n{content}\n\nКраткое резюме:', true, false, 1),
('web_detailed_ru', 'web', 'ru', 'Проанализируйте эту статью и предоставьте подробное резюме на русском языке с основными моментами, ключевыми аргументами и выводами:\n\n{content}\n\nПодробное резюме:', true, true, 1);

-- ========================================
-- TRANSLATIONS FOR UI
-- ========================================

-- French translations
INSERT INTO translations (key, language, value, context) VALUES
-- Welcome messages
('welcome_message', 'fr', '🎉 Bienvenue sur SamBot !\n\nJe suis votre assistant IA pour créer des résumés intelligents de vidéos YouTube et d''articles web.\n\n🔗 Envoyez-moi simplement un lien et je vous ferai un résumé !', 'First message to new users'),
('help_message', 'fr', '📖 *Aide SamBot*\n\n🔗 Envoyez un lien YouTube ou d''article web\n📝 Recevez un résumé intelligent\n⚙️ /settings - Paramètres\n💎 /upgrade - Plans premium\n\n*Langues supportées :* Français, English, Русский', 'Help command response'),

-- Plan names
('plan_free_name', 'fr', '🆓 Gratuit', 'Free plan name'),
('plan_premium_name', 'fr', '💎 Premium', 'Premium plan name'),
('plan_vip_name', 'fr', '👑 VIP', 'VIP plan name'),

-- Plan descriptions
('plan_free_desc', 'fr', '5 résumés par jour\nRésumés standard\nSupport communautaire', 'Free plan description'),
('plan_premium_desc', 'fr', '50 résumés par jour\nRésumés détaillés\nSupport prioritaire\nChoix de longueur', 'Premium plan description'),
('plan_vip_desc', 'fr', 'Résumés illimités\nPrompts personnalisés\nAccès API\nSupport téléphonique', 'VIP plan description'),

-- Error messages
('error_limit_reached', 'fr', '⚠️ Limite quotidienne atteinte !\n\n🆓 Gratuit : 5 résumés/jour\n💎 Premium : 50 résumés/jour\n👑 VIP : Illimité\n\n/upgrade pour plus de résumés', 'Daily limit error'),
('error_invalid_url', 'fr', '❌ URL non valide\n\nVeuillez envoyer un lien YouTube ou d''article web valide.', 'Invalid URL error');

-- English translations
INSERT INTO translations (key, language, value, context) VALUES
-- Welcome messages
('welcome_message', 'en', '🎉 Welcome to SamBot!\n\nI''m your AI assistant for creating smart summaries of YouTube videos and web articles.\n\n🔗 Just send me a link and I''ll create a summary!', 'First message to new users'),
('help_message', 'en', '📖 *SamBot Help*\n\n🔗 Send a YouTube or web article link\n📝 Get an intelligent summary\n⚙️ /settings - Settings\n💎 /upgrade - Premium plans\n\n*Supported languages:* Français, English, Русский', 'Help command response'),

-- Plan names  
('plan_free_name', 'en', '🆓 Free', 'Free plan name'),
('plan_premium_name', 'en', '💎 Premium', 'Premium plan name'),
('plan_vip_name', 'en', '👑 VIP', 'VIP plan name'),

-- Plan descriptions
('plan_free_desc', 'en', '5 summaries per day\nStandard summaries\nCommunity support', 'Free plan description'),
('plan_premium_desc', 'en', '50 summaries per day\nDetailed summaries\nPriority support\nLength options', 'Premium plan description'),
('plan_vip_desc', 'en', 'Unlimited summaries\nCustom prompts\nAPI access\nPhone support', 'VIP plan description'),

-- Error messages
('error_limit_reached', 'en', '⚠️ Daily limit reached!\n\n🆓 Free: 5 summaries/day\n💎 Premium: 50 summaries/day\n👑 VIP: Unlimited\n\n/upgrade for more summaries', 'Daily limit error'),
('error_invalid_url', 'en', '❌ Invalid URL\n\nPlease send a valid YouTube or web article link.', 'Invalid URL error');

-- Russian translations
INSERT INTO translations (key, language, value, context) VALUES
-- Welcome messages
('welcome_message', 'ru', '🎉 Добро пожаловать в SamBot!\n\nЯ ваш ИИ-помощник для создания умных резюме YouTube видео и веб-статей.\n\n🔗 Просто отправьте мне ссылку, и я создам резюме!', 'First message to new users'),
('help_message', 'ru', '📖 *Помощь SamBot*\n\n🔗 Отправьте ссылку на YouTube или статью\n📝 Получите умное резюме\n⚙️ /settings - Настройки\n💎 /upgrade - Премиум планы\n\n*Поддерживаемые языки:* Français, English, Русский', 'Help command response'),

-- Plan names
('plan_free_name', 'ru', '🆓 Бесплатный', 'Free plan name'),
('plan_premium_name', 'ru', '💎 Премиум', 'Premium plan name'),  
('plan_vip_name', 'ru', '👑 VIP', 'VIP plan name'),

-- Plan descriptions
('plan_free_desc', 'ru', '5 резюме в день\nСтандартные резюме\nПоддержка сообщества', 'Free plan description'),
('plan_premium_desc', 'ru', '50 резюме в день\nДетальные резюме\nПриоритетная поддержка\nВыбор длины', 'Premium plan description'),
('plan_vip_desc', 'ru', 'Безлимитные резюме\nПерсональные промпты\nДоступ к API\nТелефонная поддержка', 'VIP plan description'),

-- Error messages
('error_limit_reached', 'ru', '⚠️ Дневной лимит достигнут!\n\n🆓 Бесплатный: 5 резюме/день\n💎 Премиум: 50 резюме/день\n👑 VIP: Безлимит\n\n/upgrade для большего количества резюме', 'Daily limit error'),
('error_invalid_url', 'ru', '❌ Неверная ссылка\n\nПожалуйста, отправьте корректную ссылку на YouTube или веб-статью.', 'Invalid URL error');