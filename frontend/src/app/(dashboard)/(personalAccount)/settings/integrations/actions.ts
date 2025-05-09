'use server';

import { createClient } from '@/lib/supabase/server'; // Server client for actions
import { revalidatePath } from 'next/cache';
//TODO: Implement encryption/decryption for tokens
// Encryption has been removed for development ease as per user request.
// IMPORTANT: This is INSECURE and should NOT be used in production.
// Re-implement robust encryption before any production deployment.

interface GoogleIntegrationData {
  provider_access_token?: string | null;
  provider_refresh_token?: string | null;
  expires_in?: number | null; // From Google, in seconds
  scopes: string[];
  provider_user_id: string;
}

export async function upsertGoogleIntegration(
  data: GoogleIntegrationData
) {
  const supabase = await createClient();

  const { data: { user }, error: userError } = await supabase.auth.getUser();

  if (userError || !user) {
    console.error('Error fetching user or no user logged in:', userError);
    return { error: 'User not authenticated' };
  }

  const { 
    provider_access_token,
    provider_refresh_token, 
    expires_in,
    scopes,
    provider_user_id
  } = data;

  // Tokens are passed directly without encryption for development.
  const directAccessToken = provider_access_token;
  const directRefreshToken = provider_refresh_token;

  let tokenExpiresAt: Date | null = null;
  if (expires_in) {
    tokenExpiresAt = new Date(Date.now() + expires_in * 1000);
  }

  // Call the RPC function
  const { data: rpcResult, error: rpcError } = await supabase.rpc(
    'upsert_google_user_integration',
    {
      p_user_id: user.id,
      p_provider_user_id: provider_user_id,
      p_scopes: scopes,
      // Passing plaintext tokens to columns intended for encrypted data.
      p_encrypted_access_token: directAccessToken,
      p_encrypted_refresh_token: directRefreshToken,
      p_token_expires_at: tokenExpiresAt ? tokenExpiresAt.toISOString() : null,
    }
  );

  if (rpcError) {
    console.error('Error calling upsert_google_user_integration RPC:', rpcError);
    return { error: rpcError.message };
  }
  
  const integrationData = rpcResult && Array.isArray(rpcResult) && rpcResult.length > 0 ? rpcResult[0] : null;

  if (!integrationData) {
    console.warn('upsert_google_user_integration RPC did not return expected data.', rpcResult);
  }

  revalidatePath('/settings/integrations');
  return { success: true, data: integrationData };
}

export async function disconnectGoogleIntegration() {
  const supabase = await createClient();
  const { data: { user }, error: userError } = await supabase.auth.getUser();

  if (userError || !user) {
    return { error: 'User not authenticated' };
  }

  const { error: updateError } = await supabase
    .from('user_integrations') 
    .update({
      status: 'disconnected',
      scopes: null,
      provider_access_token_encrypted: null, 
      provider_refresh_token_encrypted: null,
      token_expires_at: null,
      provider_user_id: null, 
      updated_at: new Date().toISOString(),
    })
    .eq('user_id', user.id)
    .eq('provider', 'google');

  if (updateError) {
    console.error('Error disconnecting Google integration:', updateError);
    return { error: updateError.message };
  }
  
  revalidatePath('/settings/integrations');
  return { success: true };
}

// --- Placeholder for backend token retrieval and refresh logic (to be implemented in Python/FastAPI) ---
// Your Python backend will need:
// 1. The same TOKEN_ENCRYPTION_KEY.
// 2. A compatible decryptToken function.
// 3. Logic to call Google's token endpoint to refresh the access_token using the refresh_token.
// Example of what that Python function might look like conceptually (getGoogleTokensForUser):
//   - Fetch encrypted tokens from DB.
//   - Decrypt them.
//   - If access_token is expired, use refresh_token to get a new one from Google.
//   - Encrypt and update the new access_token and its expiry in the DB.
//   - Return the valid access_token.

// --- TODO: Function to get and refresh tokens for backend use ---
// export async function getGoogleTokensForUser(userId: string): Promise<{ accessToken: string | null, refreshToken: string | null }> {
//   const supabase = await createClient(); // Use admin client if necessary from a secure backend context
//   const { data, error } = await supabase
//     .from('user_integrations')
//     .select('provider_access_token_encrypted, provider_refresh_token_encrypted, token_expires_at')
//     .eq('user_id', userId)
//     .eq('provider', 'google')
//     .eq('status', 'connected')
//     .single();

//   if (error || !data) {
//     console.error('No Google integration found or error fetching for user:', userId, error);
//     return { accessToken: null, refreshToken: null };
//   }

//   let accessToken = data.provider_access_token_encrypted ? decryptToken(data.provider_access_token_encrypted) : null;
//   const refreshToken = data.provider_refresh_token_encrypted ? decryptToken(data.provider_refresh_token_encrypted) : null;

//   // Check if access token is expired or close to expiring (e.g., within 5 minutes)
//   if (accessToken && data.token_expires_at) {
//     const expiresAt = new Date(data.token_expires_at).getTime();
//     const fiveMinutes = 5 * 60 * 1000;
//     if (expiresAt < Date.now() + fiveMinutes) {
//       // Access token is expired or expiring soon, try to refresh
//       if (refreshToken) {
//         console.log('Access token expired, attempting refresh for user:', userId);
//         // TODO: Implement Google token refresh logic using the refreshToken
//         // This involves making a POST request to https://oauth2.googleapis.com/token
//         // with grant_type='refresh_token', client_id, client_secret, refresh_token.
//         // Update the new access_token (and its new expiry) in your database (encrypted).
//         // For example:
//         // const refreshed = await refreshGoogleAccessToken(refreshToken);
//         // if (refreshed) {
//         //   accessToken = refreshed.accessToken;
//         //   await supabase.from('user_integrations').update({ 
//         //     provider_access_token_encrypted: encryptToken(refreshed.accessToken),
//         //     token_expires_at: new Date(Date.now() + refreshed.expires_in * 1000).toISOString(),
//         //     updated_at: new Date().toISOString(),
//         //   }).eq('user_id', userId).eq('provider', 'google');
//         // } else {
//         //   accessToken = null; // Refresh failed
//         // }
//         accessToken = null; // Placeholder: clear token if expired and refresh not implemented
//         console.warn('Google access token refresh logic not implemented.');
//       } else {
//         accessToken = null; // No refresh token available
//       }
//     }
//   }
//   return { accessToken, refreshToken };
// } 