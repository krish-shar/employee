CREATE TABLE user_integrations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    provider TEXT NOT NULL, -- e.g., 'google'
    provider_user_id TEXT, -- User's ID from the provider
    status TEXT NOT NULL DEFAULT 'disconnected', -- e.g., 'connected', 'disconnected', 'error'
    scopes JSONB, -- Store granted scopes as a JSON array of strings
    -- For storing tokens directly, ensure they are encrypted at rest.
    -- Consider if Supabase session management is sufficient before storing these.
    -- provider_access_token_encrypted TEXT, 
    -- provider_refresh_token_encrypted TEXT,
    -- token_expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, provider)
);

-- Optional: Create a trigger to automatically update 'updated_at'
CREATE OR REPLACE FUNCTION trigger_set_timestamp()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER set_user_integrations_updated_at
BEFORE UPDATE ON user_integrations
FOR EACH ROW
EXECUTE FUNCTION trigger_set_timestamp();

-- Enable Row-Level Security (RLS) for the table
ALTER TABLE user_integrations ENABLE ROW LEVEL SECURITY;

-- Policy: Users can view their own integrations
CREATE POLICY "Allow users to view their own integrations"
ON user_integrations
FOR SELECT
USING (auth.uid() = user_id);

-- Policy: Users can insert their own integrations
CREATE POLICY "Allow users to insert their own integrations"
ON user_integrations
FOR INSERT
WITH CHECK (auth.uid() = user_id);

-- Policy: Users can update their own integrations
CREATE POLICY "Allow users to update their own integrations"
ON user_integrations
FOR UPDATE
USING (auth.uid() = user_id)
WITH CHECK (auth.uid() = user_id);

-- Policy: Users can delete their own integrations (optional, for disconnect)
CREATE POLICY "Allow users to delete their own integrations"
ON user_integrations
FOR DELETE
USING (auth.uid() = user_id);

COMMENT ON COLUMN user_integrations.provider_user_id IS 'User''s unique identifier from the OAuth provider.';
COMMENT ON COLUMN user_integrations.scopes IS 'JSON array of scopes granted by the user, e.g., ["email", "profile", "calendar.readonly"].';
-- COMMENT ON COLUMN user_integrations.provider_access_token_encrypted IS 'Encrypted OAuth access token from the provider.';
-- COMMENT ON COLUMN user_integrations.provider_refresh_token_encrypted IS 'Encrypted OAuth refresh token from the provider.';
-- COMMENT ON COLUMN user_integrations.token_expires_at IS 'Timestamp when the access token expires.'; 