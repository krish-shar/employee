CREATE OR REPLACE FUNCTION upsert_google_user_integration(
    p_user_id UUID,
    p_provider_user_id TEXT,
    p_scopes JSONB,
    p_encrypted_access_token TEXT,
    p_encrypted_refresh_token TEXT,
    p_token_expires_at TIMESTAMPTZ
)
RETURNS SETOF user_integrations -- Returns the affected row(s)
LANGUAGE plpgsql
-- The function will run with the permissions of the user calling it (invoker security).
-- RLS policies on user_integrations must allow INSERT and UPDATE for the user.
AS $$
BEGIN
    RETURN QUERY
    INSERT INTO public.user_integrations (
        user_id,
        provider,
        provider_user_id,
        status,
        scopes,
        provider_access_token_encrypted,
        provider_refresh_token_encrypted,
        token_expires_at,
        updated_at -- created_at has a default value and is set on insert
    )
    VALUES (
        p_user_id,
        'google', -- Provider is hardcoded to 'google' for this specific function
        p_provider_user_id,
        'connected', -- Status is set to 'connected' by this operation
        p_scopes,
        p_encrypted_access_token,
        p_encrypted_refresh_token,
        p_token_expires_at,
        NOW()
    )
    ON CONFLICT (user_id, provider) DO UPDATE SET
        provider_user_id = EXCLUDED.provider_user_id,
        status = EXCLUDED.status, -- Should be 'connected'
        scopes = EXCLUDED.scopes,
        provider_access_token_encrypted = EXCLUDED.provider_access_token_encrypted,
        provider_refresh_token_encrypted = EXCLUDED.provider_refresh_token_encrypted,
        token_expires_at = EXCLUDED.token_expires_at,
        updated_at = NOW()
    RETURNING *;
END;
$$;

COMMENT ON FUNCTION upsert_google_user_integration(UUID, TEXT, JSONB, TEXT, TEXT, TIMESTAMPTZ) 
IS 'Inserts or updates a Google integration for a user. Handles conflicts on (user_id, provider).'; 