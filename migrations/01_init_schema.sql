-- ========================================
-- SamBot 2.0 Database Schema
-- PostgreSQL + pgvector for RAG
-- Migrated from SQLite with enhancements
-- ========================================

-- Enable pgvector extension for embeddings
CREATE EXTENSION IF NOT EXISTS vector;

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ========================================
-- USERS & SUBSCRIPTIONS
-- ========================================

-- Main users table
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    username VARCHAR(255),
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    language_code VARCHAR(10) DEFAULT 'fr',
    subscription_type VARCHAR(50) DEFAULT 'free',
    subscription_expires_at TIMESTAMP,
    total_requests INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_blocked BOOLEAN DEFAULT false,
    country_code VARCHAR(10) DEFAULT 'FR',
    timezone VARCHAR(100) DEFAULT 'Europe/Paris'
);

-- Subscription plans with multi-currency support
CREATE TABLE subscription_plans (
    id SERIAL PRIMARY KEY,
    name_key VARCHAR(100) NOT NULL,
    price_eur_cents INTEGER,
    price_usd_cents INTEGER,
    price_rub_cents INTEGER,
    duration_days INTEGER,
    daily_requests_limit INTEGER,
    features JSONB,
    is_active BOOLEAN DEFAULT true,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Usage tracking per user per day
CREATE TABLE usage_stats (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    requests_count INTEGER DEFAULT 0,
    tokens_used INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, date)
);

-- Payment transactions
CREATE TABLE payments (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plan_id INTEGER NOT NULL REFERENCES subscription_plans(id),
    amount_eur_cents INTEGER,
    currency VARCHAR(10) DEFAULT 'EUR',
    payment_method VARCHAR(50),
    external_payment_id VARCHAR(255),
    status VARCHAR(50) DEFAULT 'pending',
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

-- ========================================
-- CONTENT & PROMPTS
-- ========================================

-- Prompt templates with i18n support
CREATE TABLE prompt_templates (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    content_type VARCHAR(50) NOT NULL,
    language VARCHAR(10) NOT NULL,
    template TEXT NOT NULL,
    is_active BOOLEAN DEFAULT true,
    is_default BOOLEAN DEFAULT false,
    version INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(name, content_type, language)
);

-- Original content storage
CREATE TABLE original_content (
    id SERIAL PRIMARY KEY,
    url_hash VARCHAR(64) UNIQUE NOT NULL,
    original_url TEXT NOT NULL,
    content_type VARCHAR(50) NOT NULL,
    content_hash VARCHAR(64) UNIQUE NOT NULL,
    raw_content TEXT NOT NULL,
    content_language VARCHAR(10),
    metadata JSONB,
    extraction_method VARCHAR(100),
    content_length INTEGER,
    created_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    access_count INTEGER DEFAULT 1,
    last_accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Cached summaries with multilingual support
CREATE TABLE summaries_cache (
    id SERIAL PRIMARY KEY,
    content_id INTEGER NOT NULL REFERENCES original_content(id) ON DELETE CASCADE,
    summary TEXT NOT NULL,
    summary_language VARCHAR(10) NOT NULL,
    summary_length VARCHAR(50) DEFAULT 'medium',
    prompt_id INTEGER REFERENCES prompt_templates(id),
    tokens_used INTEGER,
    created_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    access_count INTEGER DEFAULT 1,
    last_accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(content_id, summary_language, summary_length, prompt_id)
);

-- User settings with i18n
CREATE TABLE user_settings (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    preferred_language VARCHAR(10) DEFAULT 'fr',
    summary_language VARCHAR(10) DEFAULT 'fr',
    summary_length VARCHAR(50) DEFAULT 'medium',
    custom_prompt TEXT,
    notifications_enabled BOOLEAN DEFAULT true,
    timezone VARCHAR(100) DEFAULT 'Europe/Paris',
    date_format VARCHAR(50) DEFAULT 'DD/MM/YYYY',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ========================================
-- INTERNATIONALIZATION
-- ========================================

-- i18n translations table for dynamic content
CREATE TABLE translations (
    id SERIAL PRIMARY KEY,
    key VARCHAR(255) NOT NULL,
    language VARCHAR(10) NOT NULL,
    value TEXT NOT NULL,
    context TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(key, language)
);

-- Supported languages configuration
CREATE TABLE supported_languages (
    code VARCHAR(10) PRIMARY KEY,
    name_english VARCHAR(100) NOT NULL,
    name_native VARCHAR(100) NOT NULL,
    is_active BOOLEAN DEFAULT true,
    is_default BOOLEAN DEFAULT false,
    flag_emoji VARCHAR(10),
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ========================================
-- ANALYTICS & MONITORING
-- ========================================

-- Bot analytics
CREATE TABLE bot_analytics (
    id SERIAL PRIMARY KEY,
    event_type VARCHAR(100) NOT NULL,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    data JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Error logs
CREATE TABLE error_logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    error_type VARCHAR(100),
    error_message TEXT,
    stack_trace TEXT,
    url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ========================================
-- INDEXES FOR PERFORMANCE
-- ========================================

CREATE INDEX idx_users_telegram_id ON users(telegram_id);
CREATE INDEX idx_users_subscription_type ON users(subscription_type);
CREATE INDEX idx_usage_stats_user_date ON usage_stats(user_id, date);
CREATE INDEX idx_original_content_url_hash ON original_content(url_hash);
CREATE INDEX idx_original_content_content_hash ON original_content(content_hash);
CREATE INDEX idx_original_content_type_lang ON original_content(content_type, content_language);
CREATE INDEX idx_summaries_cache_content_id ON summaries_cache(content_id);
CREATE INDEX idx_summaries_cache_content_lang_length ON summaries_cache(content_id, summary_language, summary_length);
CREATE INDEX idx_translations_key_lang ON translations(key, language);
CREATE INDEX idx_bot_analytics_type_date ON bot_analytics(event_type, created_at);

-- ========================================
-- FUNCTIONS FOR AUTOMATIC UPDATES
-- ========================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers for automatic timestamp updates
CREATE TRIGGER update_users_timestamp
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_settings_timestamp
    BEFORE UPDATE ON user_settings
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_summaries_cache_timestamp
    BEFORE UPDATE ON summaries_cache
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_original_content_timestamp
    BEFORE UPDATE ON original_content
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_translations_timestamp
    BEFORE UPDATE ON translations
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ========================================
-- COMMENTS FOR DOCUMENTATION
-- ========================================

COMMENT ON TABLE users IS 'Main users table with subscription management';
COMMENT ON TABLE original_content IS 'Original extracted content from YouTube/web sources';
COMMENT ON TABLE summaries_cache IS 'Cached AI-generated summaries with multilingual support';
COMMENT ON EXTENSION vector IS 'pgvector extension for storing embeddings and similarity search';