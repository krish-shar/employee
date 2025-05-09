ALTER TABLE user_integrations
ADD COLUMN provider_access_token_encrypted TEXT,
ADD COLUMN provider_refresh_token_encrypted TEXT,
ADD COLUMN token_expires_at TIMESTAMPTZ;

COMMENT ON COLUMN user_integrations.provider_access_token_encrypted IS 'Encrypted OAuth access token. Your application MUST encrypt this.';
COMMENT ON COLUMN user_integrations.provider_refresh_token_encrypted IS 'Encrypted OAuth refresh token. Your application MUST encrypt this.';
COMMENT ON COLUMN user_integrations.token_expires_at IS 'Timestamp when the current OAuth access token expires.';

-- Note: If the table user_integrations might not exist (e.g. if the previous migration 20250508000000_create_user_integrations.sql hasn't run yet)
-- you might want to wrap the ALTER TABLE in a conditional block or ensure migrations are run in order.
-- However, Supabase CLI typically handles running migrations in sequence. 