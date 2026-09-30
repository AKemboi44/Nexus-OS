(() => {
    const SUPABASE_URL = 'https://mdjgrtkjjcwmhuhpsjsk.supabase.co';
    const SUPABASE_PUBLISHABLE_KEY = 'sb_publishable_xp5XQM7DThmmgsVpG4wZog_QVVnOOmw';
    const SESSION_KEY = 'nexus_supabase_session';
    const PKCE_KEY = 'nexus_supabase_oauth';
    let refreshInProgress = null;

    async function authRequest(path, {method = 'GET', body, accessToken} = {}) {
        const headers = {
            apikey: SUPABASE_PUBLISHABLE_KEY,
            Accept: 'application/json'
        };
        if (body) headers['Content-Type'] = 'application/json';
        if (accessToken) headers.Authorization = `Bearer ${accessToken}`;

        const response = await fetch(`${SUPABASE_URL}/auth/v1/${path}`, {
            method,
            headers,
            body: body ? JSON.stringify(body) : undefined
        });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) {
            throw new Error(payload.msg || payload.message || payload.error_description ||
                payload.error || `Supabase Auth request failed (${response.status}).`);
        }
        return payload;
    }

    async function storeSession(session) {
        if (!session?.access_token || !session?.refresh_token || !session?.user) {
            throw new Error('Supabase returned an incomplete sign-in session.');
        }
        const stored = {
            ...session,
            expires_at: session.expires_at ||
                Math.floor(Date.now() / 1000) + (session.expires_in || 3600)
        };
        const user = {
            id: stored.user.id,
            email: stored.user.email,
            provider: stored.user.app_metadata?.provider || 'email'
        };
        await chrome.storage.local.set({
            [SESSION_KEY]: stored,
            nexus_auth_user: user
        });
        return stored;
    }

    async function clearSession() {
        await chrome.storage.local.remove([SESSION_KEY, PKCE_KEY, 'nexus_auth_user']);
    }

    function refreshSession(session) {
        if (refreshInProgress) return refreshInProgress;
        refreshInProgress = (async () => {
            if (!session?.refresh_token) {
                await clearSession();
                return null;
            }
            try {
                return await storeSession(await authRequest('token?grant_type=refresh_token', {
                    method: 'POST',
                    body: {refresh_token: session.refresh_token}
                }));
            } catch (error) {
                await clearSession();
                throw error;
            } finally {
                refreshInProgress = null;
            }
        })();
        return refreshInProgress;
    }

    async function getSession() {
        const stored = await chrome.storage.local.get(SESSION_KEY);
        const session = stored[SESSION_KEY];
        if (!session) {
            await chrome.storage.local.remove('nexus_auth_user');
            return null;
        }
        if (session.expires_at <= Math.floor(Date.now() / 1000) + 60) {
            return refreshSession(session);
        }
        return session;
    }

    function encodeBase64Url(bytes) {
        let binary = '';
        bytes.forEach(byte => binary += String.fromCharCode(byte));
        return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
    }

    async function createPkcePair() {
        const random = crypto.getRandomValues(new Uint8Array(32));
        const verifier = encodeBase64Url(random);
        const digest = await crypto.subtle.digest(
            'SHA-256',
            new TextEncoder().encode(verifier)
        );
        return {verifier, challenge: encodeBase64Url(new Uint8Array(digest))};
    }

    async function signInWithGoogle() {
        const redirectTo = chrome.identity.getRedirectURL();
        const {verifier, challenge} = await createPkcePair();
        await chrome.storage.local.set({
            [PKCE_KEY]: {verifier}
        });

        const authorizeUrl = new URL(`${SUPABASE_URL}/auth/v1/authorize`);
        authorizeUrl.searchParams.set('provider', 'google');
        authorizeUrl.searchParams.set('redirect_to', redirectTo);
        authorizeUrl.searchParams.set('code_challenge', challenge);
        authorizeUrl.searchParams.set('code_challenge_method', 's256');

        let callbackUrl;
        try {
            callbackUrl = await chrome.identity.launchWebAuthFlow({
                url: authorizeUrl.toString(),
                interactive: true
            });
        } catch (error) {
            await chrome.storage.local.remove(PKCE_KEY);
            throw new Error(`Google sign-in could not complete: ${error.message}`);
        }

        const callback = new URL(callbackUrl);
        const expectedRedirect = new URL(redirectTo);
        if (callback.origin !== expectedRedirect.origin || callback.pathname !== expectedRedirect.pathname) {
            await chrome.storage.local.remove(PKCE_KEY);
            throw new Error('Google sign-in returned to an unexpected extension URL.');
        }
        const callbackError = callback.searchParams.get('error_description') ||
            callback.searchParams.get('error');
        if (callbackError) {
            await chrome.storage.local.remove(PKCE_KEY);
            throw new Error(callbackError);
        }

        const pkceData = (await chrome.storage.local.get(PKCE_KEY))[PKCE_KEY];
        const code = callback.searchParams.get('code');
        if (!code || !pkceData) {
            await chrome.storage.local.remove(PKCE_KEY);
            throw new Error('Google sign-in returned an invalid or incomplete callback.');
        }

        try {
            const session = await authRequest('token?grant_type=pkce', {
                method: 'POST',
                body: {auth_code: code, code_verifier: pkceData.verifier}
            });
            await chrome.storage.local.remove(PKCE_KEY);
            return storeSession(session);
        } catch (error) {
            await chrome.storage.local.remove(PKCE_KEY);
            throw error;
        }
    }

    async function signOut() {
        const session = await getSession();
        if (session) {
            await authRequest('logout', {accessToken: session.access_token});
        }
        await clearSession();
    }

    window.NexusAuth = {
        async signUp(email, password) {
            const result = await authRequest('signup', {
                method: 'POST',
                body: {email, password}
            });
            return result.session ? storeSession(result.session) : null;
        },
        async signIn(email, password) {
            const session = await authRequest('token?grant_type=password', {
                method: 'POST',
                body: {email, password}
            });
            return storeSession(session);
        },
        signInWithGoogle,
        getSession,
        signOut
    };
})();
