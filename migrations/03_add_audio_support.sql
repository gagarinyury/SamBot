-- Migration: Add audio file support to content extraction
-- Date: 2025-09-30

-- Add audio_file_path column to original_content
ALTER TABLE original_content
ADD COLUMN IF NOT EXISTS audio_file_path TEXT;

-- Add audio processing tracking columns
ALTER TABLE original_content
ADD COLUMN IF NOT EXISTS audio_processed BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS audio_processed_at TIMESTAMP;

-- Create index for audio cleanup queries
CREATE INDEX IF NOT EXISTS idx_audio_processed
ON original_content(audio_processed, audio_processed_at)
WHERE audio_file_path IS NOT NULL;

-- Add comments
COMMENT ON COLUMN original_content.audio_file_path IS 'Filename of downloaded audio (stored in /app/audio_storage/)';
COMMENT ON COLUMN original_content.audio_processed IS 'Flag indicating if audio has been processed by Whisper';
COMMENT ON COLUMN original_content.audio_processed_at IS 'Timestamp when audio was processed';

-- Create view for audio files pending cleanup
CREATE OR REPLACE VIEW audio_cleanup_candidates AS
SELECT
    id,
    audio_file_path,
    audio_processed_at,
    EXTRACT(EPOCH FROM (NOW() - audio_processed_at)) / 86400 as days_since_processed
FROM original_content
WHERE audio_file_path IS NOT NULL
  AND audio_processed = TRUE
  AND audio_processed_at < NOW() - INTERVAL '7 days'
ORDER BY audio_processed_at;

COMMENT ON VIEW audio_cleanup_candidates IS 'Audio files eligible for cleanup (processed > 7 days ago)';