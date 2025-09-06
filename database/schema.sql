-- ========================================
-- SamBot Database Schema v1.0
-- Multi-language Support (RU/FR/EN + extensible)
-- Euro pricing for France market
-- ========================================

-- Enable foreign key constraints
PRAGMA foreign_keys = ON;

-- ========================================
-- USERS & SUBSCRIPTIONS
-- ========================================

-- Main users table
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER UNIQUE NOT NULL,
    username TEXT,
    first_name TEXT,
    last_name TEXT,
    language_code TEXT DEFAULT 'fr',        -- 'fr', 'ru', 'en' - France default
    subscription_type TEXT DEFAULT 'free',  -- 'free' | 'premium' | 'vip'
    subscription_expires_at TIMESTAMP,
    total_requests INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_blocked BOOLEAN DEFAULT false,
    country_code TEXT DEFAULT 'FR',         -- For regional pricing
    timezone TEXT DEFAULT 'Europe/Paris'
);

-- Subscription plans with multi-currency support
CREATE TABLE subscription_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name_key TEXT NOT NULL,                 -- 'plan_free', 'plan_premium', 'plan_vip' (i18n key)
    price_eur_cents INTEGER,               -- Price in euro cents (599 EUR = 59900)
    price_usd_cents INTEGER,               -- Backup USD pricing
    price_rub_cents INTEGER,               -- Backup RUB pricing
    duration_days INTEGER,                 -- 30, 365
    daily_requests_limit INTEGER,          -- 5, 50, 999999 (unlimited)
    features TEXT,                         -- JSON: ["priority_support", "custom_prompts"]
    is_active BOOLEAN DEFAULT true,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Usage tracking per user per day
CREATE TABLE usage_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    date DATE NOT NULL,
    requests_count INTEGER DEFAULT 0,
    tokens_used INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    UNIQUE(user_id, date)
);

-- Payment transactions
CREATE TABLE payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    plan_id INTEGER NOT NULL,
    amount_eur_cents INTEGER,              -- Amount in euro cents
    currency TEXT DEFAULT 'EUR',           -- 'EUR', 'USD', 'RUB'
    payment_method TEXT,                   -- 'stripe', 'paypal', 'crypto'
    external_payment_id TEXT,              -- External payment system ID
    status TEXT DEFAULT 'pending',         -- 'pending', 'completed', 'failed', 'refunded'
    metadata TEXT,                         -- JSON with additional payment info
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    FOREIGN KEY (plan_id) REFERENCES subscription_plans (id)
);

-- ========================================
-- CONTENT & PROMPTS
-- ========================================

-- Prompt templates with i18n support
CREATE TABLE prompt_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,                    -- 'youtube_detailed', 'web_brief'
    content_type TEXT NOT NULL,            -- 'youtube' | 'web' | 'universal'
    language TEXT NOT NULL,                -- 'fr', 'ru', 'en'
    template TEXT NOT NULL,                -- Prompt template with {content} placeholders
    is_active BOOLEAN DEFAULT true,
    is_default BOOLEAN DEFAULT false,      -- Default prompt for this content_type + language
    version INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(name, content_type, language)
);

-- Cached summaries with multilingual support
CREATE TABLE summaries_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url_hash TEXT UNIQUE NOT NULL,         -- SHA256 hash of URL
    original_url TEXT NOT NULL,
    content_type TEXT NOT NULL,            -- 'youtube' | 'web'
    content_hash TEXT,                     -- Hash of actual content (for updates)
    content_language TEXT,                 -- Detected language of original content
    summary TEXT NOT NULL,
    summary_language TEXT NOT NULL,        -- Language of the summary ('fr', 'ru', 'en')
    summary_length TEXT DEFAULT 'medium',  -- 'brief' | 'medium' | 'detailed'
    prompt_id INTEGER,
    created_by_user_id INTEGER,
    tokens_used INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    access_count INTEGER DEFAULT 1,        -- How many times this cache was used
    last_accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (prompt_id) REFERENCES prompt_templates (id),
    FOREIGN KEY (created_by_user_id) REFERENCES users (id) ON DELETE SET NULL
);

-- User settings with i18n
CREATE TABLE user_settings (
    user_id INTEGER PRIMARY KEY,
    preferred_language TEXT DEFAULT 'fr',  -- 'fr', 'ru', 'en'
    summary_language TEXT DEFAULT 'fr',    -- Can be different from interface language
    summary_length TEXT DEFAULT 'medium',  -- 'brief' | 'medium' | 'detailed'
    custom_prompt TEXT,                    -- Custom prompt for VIP users
    notifications_enabled BOOLEAN DEFAULT true,
    timezone TEXT DEFAULT 'Europe/Paris',
    date_format TEXT DEFAULT 'DD/MM/YYYY', -- European format default
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);

-- ========================================
-- INTERNATIONALIZATION
-- ========================================

-- i18n translations table for dynamic content
CREATE TABLE translations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT NOT NULL,                     -- 'welcome_message', 'plan_premium_name'
    language TEXT NOT NULL,                -- 'fr', 'ru', 'en'
    value TEXT NOT NULL,                   -- Translated text
    context TEXT,                          -- Additional context for translators
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(key, language)
);

-- Supported languages configuration
CREATE TABLE supported_languages (
    code TEXT PRIMARY KEY,                 -- 'fr', 'ru', 'en'
    name_english TEXT NOT NULL,            -- 'French', 'Russian', 'English'
    name_native TEXT NOT NULL,             -- 'Français', 'Русский', 'English'
    is_active BOOLEAN DEFAULT true,
    is_default BOOLEAN DEFAULT false,
    flag_emoji TEXT,                       -- '🇫🇷', '🇷🇺', '🇬🇧'
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ========================================
-- ANALYTICS & MONITORING
-- ========================================

-- Bot analytics
CREATE TABLE bot_analytics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,             -- 'user_registered', 'summary_created', 'payment_completed'
    user_id INTEGER,
    data TEXT,                            -- JSON with event-specific data
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL
);

-- Error logs
CREATE TABLE error_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    error_type TEXT,                      -- 'api_error', 'extraction_error', 'payment_error'
    error_message TEXT,
    stack_trace TEXT,
    url TEXT,                             -- URL that caused error (if applicable)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL
);

-- ========================================
-- INDEXES FOR PERFORMANCE
-- ========================================

CREATE INDEX idx_users_telegram_id ON users(telegram_id);
CREATE INDEX idx_users_subscription_type ON users(subscription_type);
CREATE INDEX idx_usage_stats_user_date ON usage_stats(user_id, date);
CREATE INDEX idx_summaries_cache_url_hash ON summaries_cache(url_hash);
CREATE INDEX idx_summaries_cache_content_type_lang ON summaries_cache(content_type, summary_language);
CREATE INDEX idx_translations_key_lang ON translations(key, language);
CREATE INDEX idx_bot_analytics_type_date ON bot_analytics(event_type, created_at);

-- ========================================
-- TRIGGERS FOR AUTOMATIC UPDATES
-- ========================================

-- Update updated_at timestamp on users table changes
CREATE TRIGGER update_users_timestamp 
    AFTER UPDATE ON users
    BEGIN
        UPDATE users SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
    END;

-- Update updated_at timestamp on user_settings changes
CREATE TRIGGER update_user_settings_timestamp 
    AFTER UPDATE ON user_settings
    BEGIN
        UPDATE user_settings SET updated_at = CURRENT_TIMESTAMP WHERE user_id = NEW.user_id;
    END;

-- Update updated_at and last_accessed_at on cache access
CREATE TRIGGER update_cache_access 
    AFTER UPDATE OF access_count ON summaries_cache
    BEGIN
        UPDATE summaries_cache 
        SET updated_at = CURRENT_TIMESTAMP, last_accessed_at = CURRENT_TIMESTAMP 
        WHERE id = NEW.id;
    END;