GRANT EXECUTE 
ON FUNCTION public.upsert_google_user_integration(UUID, TEXT, JSONB, TEXT, TEXT, TIMESTAMPTZ) 
TO authenticated;

-- Optionally, if you want any user (even unauthenticated, though not typical for this function) to call it:
-- GRANT EXECUTE ON FUNCTION public.upsert_google_user_integration(UUID, TEXT, JSONB, TEXT, TEXT, TIMESTAMPTZ) TO public;

COMMENT ON FUNCTION public.upsert_google_user_integration(UUID, TEXT, JSONB, TEXT, TEXT, TIMESTAMPTZ) 
IS 'Grants execute permission to the authenticated role for upserting Google integrations.'; 