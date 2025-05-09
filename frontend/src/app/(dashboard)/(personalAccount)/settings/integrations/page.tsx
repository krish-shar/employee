'use client';

import { useEffect, useState, useCallback } from 'react';
import { createClient } from '@/lib/supabase/client'; // Client-side Supabase
import { Separator } from '@/components/ui/separator';
import { Button } from '@/components/ui/button';
import { upsertGoogleIntegration, disconnectGoogleIntegration } from './actions';
import { User } from '@supabase/supabase-js';
import { ExternalLink, CheckCircle, XCircle, AlertTriangle, Loader2 } from 'lucide-react';

interface IntegrationStatus {
  provider: string;
  connected: boolean;
  scopes?: string[];
  lastChecked?: Date;
}

const GOOGLE_SCOPES = [
  'openid',
  'https://www.googleapis.com/auth/userinfo.email',
  'https://www.googleapis.com/auth/userinfo.profile',
  'https://www.googleapis.com/auth/calendar', // Full access to calendars
  'https://www.googleapis.com/auth/drive',    // Full access to Drive files
  'https://www.googleapis.com/auth/gmail.modify', // Read, compose, send, and permanently delete all email
];

function PersonalSettingsIntegrationsPage() {
  const supabase = createClient();
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [googleIntegration, setGoogleIntegration] = useState<IntegrationStatus | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [actionError, setActionError] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);

  const fetchIntegrationStatus = useCallback(async (user: User | null) => {
    if (!user) {
      setGoogleIntegration(null);
      setIsLoading(false);
      return;
    }
    try {
      const { data, error } = await supabase
        .from('user_integrations')
        .select('status, scopes')
        .eq('user_id', user.id)
        .eq('provider', 'google')
        .maybeSingle();

      if (error) throw error;

      if (data) {
        setGoogleIntegration({
          provider: 'google',
          connected: data.status === 'connected',
          scopes: data.scopes as string[],
          lastChecked: new Date(),
        });
      } else {
        setGoogleIntegration({
          provider: 'google',
          connected: false,
          lastChecked: new Date(),
        });
      }
    } catch (err: any) {
      console.error('Error fetching integration status:', err);
      setActionError('Failed to load integration status: ' + err.message);
      setGoogleIntegration({ provider: 'google', connected: false });
    } finally {
      setIsLoading(false);
    }
  }, [supabase]);

  useEffect(() => {
    const { data: authListener } = supabase.auth.onAuthStateChange(async (event, session) => {
      const user = session?.user ?? null;
      setCurrentUser(user);
      fetchIntegrationStatus(user);

      if (event === 'SIGNED_IN' && session?.provider_token) {
        // This event fires after OAuth redirect AND when session is refreshed.
        // We only want to process this as a new integration if it seems like a fresh OAuth callback.
        // A more robust check might involve a nonce or state parameter passed through OAuth.
        if (session.user && session.user.identities) {
            const googleIdentity = session.user.identities.find(id => id.provider === 'google');
            if (googleIdentity && !googleIntegration?.connected) { // Avoid re-processing if already connected
                setIsProcessing(true);
                setActionError(null);
                try {
                    console.log('Attempting to upsert Google integration...');
                    console.log('Session details:', session);
                    
                    // Extract the actual granted scopes. For Google, this is tricky client-side post-redirect without another call.
                    // We will assume requested scopes were granted for now. If Google returns scopes in fragment, handle that.
                    // Supabase session.provider_token might be the Google access_token.
                    // session.provider_refresh_token is what we would ideally store securely.

                    const result = await upsertGoogleIntegration({
                        provider_access_token: session.provider_token, // This is the access token
                        provider_refresh_token: session.provider_refresh_token, // This might be available
                        expires_in: session.expires_in, // Pass expires_in if available from Supabase session
                        scopes: GOOGLE_SCOPES, // Assume requested scopes are granted
                        provider_user_id: googleIdentity.id,
                    });

                    if (result.error) {
                        throw new Error(result.error);
                    }
                    console.log('Upsert successful', result);
                    await fetchIntegrationStatus(session.user); // Refresh status
                } catch (error: any) {
                    console.error('Error processing Google Sign In:', error);
                    setActionError('Error connecting Google Account: ' + error.message);
                } finally {
                    setIsProcessing(false);
                    // Clean the URL if parameters are present from OAuth redirect
                    if (window.location.hash.includes('provider_token') || window.location.search.includes('code')) {
                        window.history.replaceState({}, document.title, window.location.pathname);
                    }
                }
            }
        }
      } else if (event === 'SIGNED_OUT') {
        setCurrentUser(null);
        setGoogleIntegration(null);
      }
    });

    // Initial check
    supabase.auth.getUser().then(({ data: { user } }) => {
        setCurrentUser(user);
        fetchIntegrationStatus(user);
    });

    return () => {
      authListener.subscription.unsubscribe();
    };
  }, [supabase, fetchIntegrationStatus, googleIntegration?.connected]);

  const handleConnectGoogle = async () => {
    if (!currentUser) {
      setActionError('Please ensure you are logged in first.');
      return;
    }
    setIsProcessing(true);
    setActionError(null);
    const { error } = await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: {
        scopes: GOOGLE_SCOPES.join(' '),
        redirectTo: window.location.href, // Redirect back to this page
        queryParams: {
          access_type: 'offline',
          prompt: 'consent',
        },
      },
    });
    if (error) {
      console.error('Error initiating Google OAuth:', error);
      setActionError('Could not connect with Google: ' + error.message);
      setIsProcessing(false);
    }
    // Redirect happens in browser, processing continues in useEffect after redirect
  };

  const handleDisconnectGoogle = async () => {
    if (!currentUser) {
      setActionError('User not found.');
      return;
    }
    setIsProcessing(true);
    setActionError(null);
    const result = await disconnectGoogleIntegration();
    if (result.error) {
      setActionError('Failed to disconnect: ' + result.error);
    } else {
      await fetchIntegrationStatus(currentUser); // Refresh status
    }
    setIsProcessing(false);
  };

  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-32">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className='flex flex-col gap-6 p-4 md:p-6'>
      <div className='flex flex-col gap-2'>
        <h1 className='text-2xl font-bold'>Integrations</h1>
        <p className='text-sm text-muted-foreground'>Connect your accounts to sync your data and enable new features.</p>
      </div>
      <Separator />

      {actionError && (
        <div className="p-4 rounded-md bg-destructive/10 border border-destructive/20 text-destructive flex items-center gap-3">
          <AlertTriangle className="h-5 w-5 flex-shrink-0" />
          <span className="text-sm font-medium">{actionError}</span>
        </div>
      )}

      {/* Google Integration Card */}
      <div className="border rounded-lg p-6 shadow-sm bg-card">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <img src="https://upload.wikimedia.org/wikipedia/commons/c/c1/Google_%22G%22_logo.svg" alt="Google Logo" className="h-10 w-10" />
            <div>
              <h2 className="text-xl font-semibold">Google</h2>
              <p className="text-sm text-muted-foreground">
                Connect your Google Account to access Calendar, Drive, and Gmail.
              </p>
            </div>
          </div>
          {googleIntegration?.connected ? (
            <Button variant="outline" onClick={handleDisconnectGoogle} disabled={isProcessing}>
              {isProcessing ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <XCircle className="mr-2 h-4 w-4" />}
              Disconnect
            </Button>
          ) : (
            <Button onClick={handleConnectGoogle} disabled={isProcessing}>
              {isProcessing ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <ExternalLink className="mr-2 h-4 w-4" />}
              Connect Google Account
            </Button>
          )}
        </div>
        {googleIntegration?.connected && googleIntegration.scopes && (
          <div className="mt-4 pt-4 border-t">
            <h3 className="text-sm font-medium text-muted-foreground mb-2">Permissions Granted:</h3>
            <div className="flex flex-wrap gap-2">
              {googleIntegration.scopes.map(scope => {
                let shortScope = scope.replace('https://www.googleapis.com/auth/', '');
                shortScope = shortScope.replace('userinfo.','');
                if (scope === 'openid') shortScope = 'OpenID (Basic Login)';
                return (
                  <span key={scope} className="text-xs bg-muted text-muted-foreground px-2 py-1 rounded-full flex items-center gap-1">
                    <CheckCircle className="h-3 w-3 text-green-500" />
                    {shortScope}
                  </span>
                );
              })}
            </div>
            <p className="mt-3 text-xs text-muted-foreground">
                You can manage permissions for this app in your <a href="https://myaccount.google.com/permissions" target="_blank" rel="noopener noreferrer" className="underline hover:text-primary">Google Account settings</a>.
            </p>
          </div>
        )}
        <div className="mt-4 text-xs text-muted-foreground">
            <p className="font-semibold">Important:</p>
            <ul className="list-disc list-inside pl-4 mt-1 space-y-1">
                <li>Connecting your Google account will grant this application access to read, create, modify, and delete (where applicable) data in your Google Calendar, Google Drive, and Gmail, as per the permissions you approve.</li>
                <li>This application will use this access to provide integrated features.</li>
                <li>We are requesting <code className='text-xs'>access_type=offline</code>, which means our application can access your data even when you are not actively using it, to perform tasks like background synchronization.</li>
            </ul>
        </div>
      </div>
      
      {/* Placeholder for other integrations */}
      {/* <Separator className="my-6" /> */}
      {/* <div> <h2 className="text-lg font-semibold">Other Integrations</h2> <p className="text-sm text-muted-foreground">More integrations coming soon!</p> </div> */}
    </div>
  );
}

export default PersonalSettingsIntegrationsPage;