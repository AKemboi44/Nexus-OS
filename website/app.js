(() => {
    'use strict';

    const SUPABASE_URL = 'https://mdjgrtkjjcwmhuhpsjsk.supabase.co';
    const SUPABASE_PUBLISHABLE_KEY = 'sb_publishable_xp5XQM7DThmmgsVpG4wZog_QVVnOOmw';
    const API_URL = 'https://nexus-os-production-2e14.up.railway.app';
    const SESSION_KEY = 'nexus_web_supabase_session';
    const PKCE_KEY = 'nexus_web_supabase_pkce';
    const FREE_MAX_SOURCES = 20;
    const SESSION_TICK_MARGIN_SECONDS = 60;

    const byId = id => document.getElementById(id);
    const dialog = byId('authDialog');
    const authStatus = byId('authStatus');
    const scanStatus = byId('scanStatus');
    const reportStatus = byId('reportStatus');
    let session = null;
    let paid = false;
    let authMode = 'signin';
    let activeResult = null;

    function setMessage(element, message, type = '') {
        if (!element) return;
        element.textContent = message;
        element.className = `form-message${type ? ` ${type}` : ''}`;
    }

    async function readAuthResponse(response) {
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            throw new Error(data.msg || data.message || data.error_description || data.error ||
                `Authentication failed (${response.status}).`);
        }
        return data;
    }

    async function authRequest(path, {method = 'GET', body, accessToken} = {}) {
        const headers = {apikey: SUPABASE_PUBLISHABLE_KEY, Accept: 'application/json'};
        if (body) headers['Content-Type'] = 'application/json';
        if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
        const response = await fetch(`${SUPABASE_URL}/auth/v1/${path}`, {
            method,
            headers,
            body: body ? JSON.stringify(body) : undefined
        });
        return readAuthResponse(response);
    }

    function persistSession(nextSession) {
        if (!nextSession?.access_token || !nextSession?.refresh_token || !nextSession?.user) {
            throw new Error('The sign-in response did not include a complete session.');
        }
        session = {
            ...nextSession,
            expires_at: nextSession.expires_at ||
                Math.floor(Date.now() / 1000) + (nextSession.expires_in || 3600)
        };
        localStorage.setItem(SESSION_KEY, JSON.stringify(session));
        return session;
    }

    function clearSession() {
        session = null;
        localStorage.removeItem(SESSION_KEY);
        sessionStorage.removeItem(PKCE_KEY);
    }

    async function refreshSession() {
        if (!session?.refresh_token) {
            clearSession();
            return null;
        }
        try {
            return persistSession(await authRequest('token?grant_type=refresh_token', {
                method: 'POST',
                body: {refresh_token: session.refresh_token}
            }));
        } catch (error) {
            clearSession();
            throw error;
        }
    }

    async function getSession() {
        if (!session) {
            try {
                session = JSON.parse(localStorage.getItem(SESSION_KEY) || 'null');
            } catch (error) {
                clearSession();
                throw new Error('Stored sign-in data was invalid. Please sign in again.');
            }
        }
        if (!session) return null;
        if (session.expires_at <= Math.floor(Date.now() / 1000) + SESSION_TICK_MARGIN_SECONDS) {
            return refreshSession();
        }
        return session;
    }

    async function exchangeCallback() {
        const url = new URL(window.location.href);
        const code = url.searchParams.get('code');
        const oauthError = url.searchParams.get('error_description') || url.searchParams.get('error');
        const hash = new URLSearchParams(url.hash.slice(1));
        if (oauthError) throw new Error(oauthError);
        if (code) {
            const verifier = sessionStorage.getItem(PKCE_KEY);
            if (!verifier) throw new Error('The Google sign-in session expired. Please try again.');
            const exchanged = await authRequest('token?grant_type=pkce', {
                method: 'POST',
                body: {auth_code: code, code_verifier: verifier}
            });
            persistSession(exchanged);
            sessionStorage.removeItem(PKCE_KEY);
            window.history.replaceState({}, document.title, `${url.pathname}${url.hash}`);
            return true;
        }
        const accessToken = hash.get('access_token');
        const refreshToken = hash.get('refresh_token');
        if (accessToken && refreshToken) {
            const user = await authRequest('user', {accessToken});
            persistSession({
                access_token: accessToken,
                refresh_token: refreshToken,
                expires_in: Number(hash.get('expires_in') || 3600),
                user
            });
            window.history.replaceState({}, document.title, url.pathname);
            return true;
        }
        return false;
    }

    function base64Url(bytes) {
        let binary = '';
        bytes.forEach(byte => { binary += String.fromCharCode(byte); });
        return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
    }

    async function googleSignIn() {
        const verifier = base64Url(crypto.getRandomValues(new Uint8Array(32)));
        const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier));
        const challenge = base64Url(new Uint8Array(digest));
        sessionStorage.setItem(PKCE_KEY, verifier);
        const authorization = new URL(`${SUPABASE_URL}/auth/v1/authorize`);
        authorization.searchParams.set('provider', 'google');
        authorization.searchParams.set('redirect_to', `${location.origin}/`);
        authorization.searchParams.set('code_challenge', challenge);
        authorization.searchParams.set('code_challenge_method', 's256');
        location.assign(authorization.toString());
    }

    function openAuth(mode = 'signin') {
        setAuthMode(mode);
        dialog.hidden = false;
        byId('authEmail').focus();
    }

    function setAuthMode(mode) {
        authMode = mode;
        const signingUp = mode === 'signup';
        byId('authSignInTab').classList.toggle('active', !signingUp);
        byId('authSignUpTab').classList.toggle('active', signingUp);
        byId('authTitle').textContent = signingUp ? 'Create your Nexus account' : 'Welcome to Nexus';
        byId('authSubmit').textContent = signingUp ? 'Create account' : 'Sign in';
        byId('authPassword').autocomplete = signingUp ? 'new-password' : 'current-password';
        setMessage(authStatus, '');
    }

    function renderAuthState() {
        const loggedIn = Boolean(session?.access_token);
        byId('signInOpen').hidden = loggedIn;
        byId('signOut').hidden = !loggedIn;
        byId('accountEmail').textContent = session?.user?.email || 'researcher';
        byId('workspace').hidden = !loggedIn;
        if (loggedIn) {
            dialog.hidden = true;
            byId('heroStart').textContent = 'Continue to workspace →';
            byId('headerStart').textContent = 'Continue researching ↗';
        } else {
            byId('heroStart').textContent = 'Start researching →';
            byId('headerStart').textContent = 'Open workspace ↗';
        }
    }

    async function apiFetch(path, options = {}) {
        let current = await getSession();
        if (!current) throw new Error('Sign in to access your research workspace.');
        const headers = new Headers(options.headers || {});
        headers.set('Authorization', `Bearer ${current.access_token}`);
        headers.set('Accept', headers.get('Accept') || 'application/json');
        if (options.body && !(options.body instanceof Blob)) headers.set('Content-Type', 'application/json');
        let response = await fetch(`${API_URL}${path}`, {...options, headers});
        if (response.status === 401) {
            current = await refreshSession();
            if (!current) throw new Error('Your session expired. Please sign in again.');
            headers.set('Authorization', `Bearer ${current.access_token}`);
            response = await fetch(`${API_URL}${path}`, {...options, headers});
        }
        return response;
    }

    async function apiJson(path, options = {}) {
        const response = await apiFetch(path, options);
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(payload.detail || payload.message || `Request failed (${response.status}).`);
        return payload;
    }

    async function refreshEntitlement() {
        const response = await apiFetch(`/v1/entitlements/${encodeURIComponent(session.user.id)}`);
        const result = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(result.detail || 'Could not refresh subscription status.');
        paid = response.ok && Boolean(result.active);
        document.querySelectorAll('[data-paid-only]').forEach(option => {
            option.disabled = !paid;
            if (!paid) option.textContent = option.textContent.replace(' · paid', ' · upgrade required');
            else option.textContent = option.textContent.replace(' · upgrade required', ' · paid');
        });
        if (!paid && Number(byId('maxSources').value) > FREE_MAX_SOURCES) byId('maxSources').value = '20';
        if (!paid && byId('domain').value === 'legal') byId('domain').value = 'scholarly';
        byId('fullReport').hidden = !paid;
        byId('upgradePlan').hidden = paid;
        byId('criteriaLimit').textContent = `(up to ${paid ? 5 : 3}, optional)`;
    }

    function appendText(parent, tag, text, className = '') {
        const element = document.createElement(tag);
        if (className) element.className = className;
        element.textContent = text || '';
        parent.appendChild(element);
        return element;
    }

    function renderHistory(runs, dossiers) {
        const container = byId('historyList');
        container.replaceChildren();
        if (!runs.length) {
            appendText(container, 'p', 'Your completed scans will appear here.', 'empty-state');
            return;
        }
        const dossierByRun = new Map(dossiers.map(item => [item.payload?.research_run_id, item]));
        runs.forEach(run => {
            const item = document.createElement('article');
            item.className = 'history-item';
            appendText(item, 'strong', run.query || 'Untitled research');
            appendText(item, 'small', run.created_at ? new Date(run.created_at).toLocaleString() : 'Saved research');
            const saved = dossierByRun.get(run.id);
            if (saved) appendText(item, 'small', `${saved.payload?.included_count ?? 0} included · ${saved.payload?.excluded_count ?? 0} filtered`);
            const open = appendText(item, 'button', 'Open saved results');
            open.type = 'button';
            open.addEventListener('click', () => loadRun(run.id));
            container.appendChild(item);
        });
    }

    async function loadHistory() {
        const [runs, dossiers, sources] = await Promise.all([
            apiJson('/v1/research?limit=30'),
            apiJson('/v1/dossiers'),
            apiJson('/v1/sources')
        ]);
        renderHistory(runs, dossiers);
        renderSavedSources(sources);
    }

    function renderSavedSources(sources) {
        const container = byId('savedSourcesList');
        container.replaceChildren();
        byId('sourceCount').textContent = String(sources.length);
        if (!sources.length) {
            appendText(container, 'p', 'Save a source from a scan to keep it here.', 'empty-state');
            return;
        }
        sources.slice(0, 8).forEach(record => {
            const row = document.createElement('div');
            row.className = 'saved-source-row';
            const source = record.source || {};
            const title = document.createElement('a');
            title.textContent = source.title || 'Saved source';
            if (source.url && /^https?:\/\//i.test(source.url)) {
                title.href = source.url;
                title.target = '_blank';
                title.rel = 'noopener noreferrer';
            }
            row.appendChild(title);
            appendText(row, 'small', [source.year, source.venue].filter(Boolean).join(' · '));
            container.appendChild(row);
        });
    }

    function makeSourceCard(source, included) {
        const card = document.createElement('article');
        card.className = 'source-item';
        appendText(card, 'strong', source.title || 'Untitled source');
        const meta = [source.authors?.slice?.(0, 2).join(', '), source.year, source.venue || source.journal]
            .filter(Boolean).join(' · ');
        appendText(card, 'p', meta || (included ? 'Included in this review.' : source.exclusion_reason || 'Filtered by the scan.'));
        if (source.abstract) appendText(card, 'p', source.abstract.slice(0, 380));
        if (source.url && /^https?:\/\//i.test(source.url)) {
            const link = appendText(card, 'a', 'View source ↗');
            link.href = source.url;
            link.target = '_blank';
            link.rel = 'noopener noreferrer';
        }
        if (included) {
            const save = appendText(card, 'button', 'Save source +', 'source-save');
            save.type = 'button';
            save.addEventListener('click', async () => {
                save.disabled = true;
                try {
                    await apiJson('/v1/sources', {method: 'POST', body: JSON.stringify({source})});
                    save.textContent = 'Saved';
                    await loadHistory();
                } catch (error) {
                    save.disabled = false;
                    setMessage(reportStatus, error.message, 'error');
                }
            });
        }
        return card;
    }

    function renderResult(data) {
        activeResult = data;
        byId('scanResults').hidden = false;
        byId('resultTitle').textContent = data.query || 'Research evidence';
        const included = Array.isArray(data.included) ? data.included : [];
        const excluded = Array.isArray(data.excluded) ? data.excluded : [];
        byId('resultSummary').textContent = `${included.length} sources included · ${excluded.length} candidates filtered`;
        byId('includedCount').textContent = `(${included.length})`;
        byId('excludedCount').textContent = `(${excluded.length})`;
        byId('includedSources').replaceChildren(...included.slice(0, 30).map(source => makeSourceCard(source, true)));
        byId('excludedSources').replaceChildren(...excluded.slice(0, 30).map(source => makeSourceCard(source, false)));
        byId('fullReport').hidden = !paid;
        setMessage(reportStatus, '');
        byId('scanResults').scrollIntoView({behavior: 'smooth', block: 'start'});
    }

    async function loadRun(runId) {
        try {
            const run = await apiJson(`/v1/research/${encodeURIComponent(runId)}`);
            renderResult({...run.result, research_run_id: run.id});
        } catch (error) {
            setMessage(scanStatus, error.message, 'error');
        }
    }

    function safeDownload(blob, filename) {
        const objectUrl = URL.createObjectURL(blob);
        const anchor = document.createElement('a');
        anchor.href = objectUrl;
        anchor.download = filename;
        document.body.appendChild(anchor);
        anchor.click();
        anchor.remove();
        window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
    }

    function base64ToBlob(encoded, mimeType) {
        const binary = atob(encoded);
        const bytes = new Uint8Array(binary.length);
        for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
        return new Blob([bytes], {type: mimeType});
    }

    async function downloadExcel() {
        if (!activeResult?.research_run_id) return;
        byId('downloadExcel').disabled = true;
        setMessage(reportStatus, 'Preparing your Excel dossier…');
        try {
            const response = await apiFetch(`/v1/research/${encodeURIComponent(activeResult.research_run_id)}/dossier`);
            if (!response.ok) {
                const error = await response.json().catch(() => ({}));
                throw new Error(error.detail || `Download failed (${response.status}).`);
            }
            safeDownload(await response.blob(), activeResult.discovery_report_name || 'research-dossier.xlsx');
            const remaining = response.headers.get('X-Dossier-Downloads-Remaining');
            setMessage(reportStatus, remaining === 'unlimited'
                ? 'Dossier downloaded. Unlimited downloads available.'
                : `Dossier downloaded. ${remaining} of 3 free downloads remaining.`, 'success');
        } catch (error) {
            setMessage(reportStatus, error.message, 'error');
        } finally {
            byId('downloadExcel').disabled = false;
        }
    }

    async function generateReport(reportType) {
        if (!activeResult) return;
        if (reportType === 'full_starter' && !paid) {
            byId('plansCard').hidden = false;
            byId('plansCard').scrollIntoView({behavior: 'smooth', block: 'center'});
            return;
        }
        const button = reportType === 'full_starter' ? byId('fullReport') : byId('proposalReport');
        button.disabled = true;
        setMessage(reportStatus, 'Preparing your Word report…');
        try {
            const report = await apiJson('/v1/reports', {
                method: 'POST',
                body: JSON.stringify({
                    topic: activeResult.query || byId('topic').value.trim(),
                    included_sources: activeResult.included || [],
                    report_type: reportType,
                    domain: byId('domain').value,
                    max_sources: Number(byId('maxSources').value)
                })
            });
            safeDownload(
                base64ToBlob(report.document_base64, 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'),
                report.document_name || 'nexus-research-report.docx'
            );
            setMessage(reportStatus, 'Your Word report is ready and downloaded.', 'success');
        } catch (error) {
            setMessage(reportStatus, error.message, 'error');
        } finally {
            button.disabled = false;
        }
    }

    async function runScan(event) {
        event.preventDefault();
        const topic = byId('topic').value.trim();
        if (!topic) return;
        const button = byId('scanSubmit');
        button.disabled = true;
        setMessage(scanStatus, 'Searching sources and reviewing evidence…');
        try {
            const data = await apiJson('/v1/scan', {
                method: 'POST',
                body: JSON.stringify({
                    topic,
                    max_sources: Number(byId('maxSources').value),
                    domain: byId('domain').value,
                    selected_inclusion_reasons: [...document.querySelectorAll('.criteria-fieldset input:checked')]
                        .map(input => input.value),
                    uploaded_sources: []
                })
            });
            renderResult(data);
            setMessage(scanStatus, 'Scan complete. Your research was saved to your account.', 'success');
            await loadHistory();
        } catch (error) {
            setMessage(scanStatus, error.message, 'error');
        } finally {
            button.disabled = false;
        }
    }

    async function signOut() {
        try {
            const current = await getSession();
            if (current) await authRequest('logout', {method: 'POST', accessToken: current.access_token});
        } finally {
            clearSession();
            paid = false;
            renderAuthState();
            byId('historyList').replaceChildren();
            byId('savedSourcesList').replaceChildren();
            byId('scanResults').hidden = true;
        }
    }

    async function startSubscription(plan) {
        const status = byId('billingStatus');
        if (!byId('billingConsent').checked) {
            setMessage(status, 'Please agree to the monthly billing terms before continuing.', 'error');
            return;
        }
        const buttons = [...document.querySelectorAll('[data-plan]')];
        buttons.forEach(button => { button.disabled = true; });
        setMessage(status, 'Opening secure PayPal checkout…');
        try {
            const subscription = await apiJson('/v1/paypal/subscriptions', {
                method: 'POST',
                body: JSON.stringify({plan})
            });
            const approvalUrl = (subscription.links || []).find(link => link.rel === 'approve')?.href;
            let approval;
            try {
                approval = new URL(approvalUrl);
            } catch (error) {
                throw new Error('PayPal did not return a valid secure approval link.');
            }
            if (approval.protocol !== 'https:' ||
                !(approval.hostname === 'paypal.com' || approval.hostname.endsWith('.paypal.com'))) {
                throw new Error('PayPal did not return a valid secure approval link.');
            }
            window.location.assign(approval.toString());
        } catch (error) {
            setMessage(status, error.message, 'error');
            buttons.forEach(button => { button.disabled = false; });
        }
    }

    function startWorkspace() {
        if (!session) {
            openAuth('signin');
            return;
        }
        byId('workspace').scrollIntoView({behavior: 'smooth', block: 'start'});
        byId('topic').focus({preventScroll: true});
    }

    async function initialize() {
        byId('copyrightYear').textContent = String(new Date().getFullYear());
        const checkoutResult = new URLSearchParams(location.search).get('checkout');
        try {
            await exchangeCallback();
            await getSession();
            renderAuthState();
            if (session) {
                try {
                    await refreshEntitlement();
                } catch (error) {
                    setMessage(scanStatus, error.message, 'error');
                }
                await loadHistory();
                if (checkoutResult === 'complete') {
                    byId('plansCard').hidden = false;
                    setMessage(byId('billingStatus'), 'PayPal approval received. Subscription activation may take a moment; refresh your workspace status shortly.', 'success');
                    byId('plansCard').scrollIntoView({behavior: 'smooth', block: 'center'});
                } else if (checkoutResult === 'cancel') {
                    byId('plansCard').hidden = false;
                    setMessage(byId('billingStatus'), 'Checkout was cancelled. No subscription was activated.', 'error');
                    byId('plansCard').scrollIntoView({behavior: 'smooth', block: 'center'});
                }
            }
        } catch (error) {
            renderAuthState();
            openAuth('signin');
            setMessage(authStatus, error.message, 'error');
        }

        ['signInOpen', 'headerStart', 'heroStart', 'featureStart', 'productOpen', 'ctaStart']
            .forEach(id => byId(id).addEventListener('click', startWorkspace));
        byId('authClose').addEventListener('click', () => { dialog.hidden = true; });
        dialog.addEventListener('click', event => { if (event.target === dialog) dialog.hidden = true; });
        document.addEventListener('keydown', event => { if (event.key === 'Escape') dialog.hidden = true; });
        byId('signOut').addEventListener('click', signOut);
        byId('authSignInTab').addEventListener('click', () => setAuthMode('signin'));
        byId('authSignUpTab').addEventListener('click', () => setAuthMode('signup'));
        byId('googleSignIn').addEventListener('click', async () => {
            try {
                setMessage(authStatus, 'Opening Google sign-in…');
                await googleSignIn();
            } catch (error) {
                setMessage(authStatus, error.message, 'error');
            }
        });
        byId('authForm').addEventListener('submit', async event => {
            event.preventDefault();
            const email = byId('authEmail').value.trim();
            const password = byId('authPassword').value;
            byId('authSubmit').disabled = true;
            try {
                if (authMode === 'signup') {
                    if (password.length < 8) throw new Error('Choose a password with at least 8 characters.');
                    const result = await authRequest('signup', {method: 'POST', body: {email, password}});
                    if (!result.session) {
                        setMessage(authStatus, 'Check your email to confirm your account, then sign in.', 'success');
                        return;
                    }
                    persistSession(result.session);
                } else {
                    persistSession(await authRequest('token?grant_type=password', {
                        method: 'POST',
                        body: {email, password}
                    }));
                }
                dialog.hidden = true;
                renderAuthState();
                try {
                    await refreshEntitlement();
                } catch (error) {
                    setMessage(scanStatus, error.message, 'error');
                }
                await loadHistory();
                startWorkspace();
            } catch (error) {
                setMessage(authStatus, error.message, 'error');
            } finally {
                byId('authSubmit').disabled = false;
            }
        });
        byId('scanForm').addEventListener('submit', runScan);
        document.querySelector('.criteria-fieldset').addEventListener('change', event => {
            const checked = document.querySelectorAll('.criteria-fieldset input:checked');
            if (checked.length > (paid ? 5 : 3)) {
                event.target.checked = false;
                setMessage(scanStatus, `Select up to ${paid ? 5 : 3} evidence criteria.`, 'error');
            }
        });
        byId('refreshHistory').addEventListener('click', async () => {
            try {
                await refreshEntitlement();
                await loadHistory();
                setMessage(scanStatus, 'Subscription status and research library refreshed.', 'success');
            } catch (error) {
                setMessage(scanStatus, error.message, 'error');
            }
        });
        byId('upgradePlan').addEventListener('click', () => {
            byId('plansCard').hidden = false;
            byId('plansCard').scrollIntoView({behavior: 'smooth', block: 'center'});
        });
        byId('closePlans').addEventListener('click', () => { byId('plansCard').hidden = true; });
        document.querySelectorAll('[data-plan]').forEach(button => {
            button.addEventListener('click', () => startSubscription(button.dataset.plan));
        });
        byId('downloadExcel').addEventListener('click', downloadExcel);
        byId('proposalReport').addEventListener('click', () => generateReport('proposal'));
        byId('fullReport').addEventListener('click', () => generateReport('full_starter'));
    }

    initialize();
})();
