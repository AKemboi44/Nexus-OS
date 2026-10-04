// extension/popup.js - Fragment 1 of 2 (UI Initializers & Defensively Locked Variables)
document.addEventListener('DOMContentLoaded', () => {
    const tabTerminalBtn = document.getElementById('tabTerminalBtn');
    const tabDashboardBtn = document.getElementById('tabDashboardBtn');
    const tabSynthesisBtn = document.getElementById('tabSynthesisBtn');

    const tabTerminalContent = document.getElementById('tabTerminalContent');
    const tabDashboardContent = document.getElementById('tabDashboardContent');
    const tabSynthesisContent = document.getElementById('tabSynthesisContent');
    const linkToSynthesisBtn = document.getElementById('linkToSynthesisBtn');

    function switchTab(target) {
        [tabTerminalBtn, tabDashboardBtn, tabSynthesisBtn].forEach(b => b?.classList.remove('active'));
        [tabTerminalContent, tabDashboardContent, tabSynthesisContent].forEach(c => c?.classList.remove('active'));

        if (target === 'hub') {
            tabTerminalBtn?.classList.add('active'); tabTerminalContent?.classList.add('active');
        } else if (target === 'dashboard') {
            tabDashboardBtn?.classList.add('active'); tabDashboardContent?.classList.add('active');
        } else if (target === 'synthesis') {
            tabSynthesisBtn?.classList.add('active'); tabSynthesisContent?.classList.add('active');
        }
    }
    if(tabTerminalBtn) tabTerminalBtn.onclick = () => switchTab('hub');
    if(tabDashboardBtn) tabDashboardBtn.onclick = () => switchTab('dashboard');
    if(tabSynthesisBtn) tabSynthesisBtn.onclick = () => switchTab('synthesis');
    if(linkToSynthesisBtn) linkToSynthesisBtn.onclick = () => switchTab('synthesis');

    const runButton = document.getElementById('runBtn');
    const btnSpinner = document.getElementById('btnSpinner');
    const btnText = document.getElementById('btnText');
    const statusDiv = document.getElementById('status');
    const auditTableBody = document.querySelector('#auditTable tbody');
    const banner = document.getElementById('tierBanner');
    const countInc = document.getElementById('countInc');
    const countExc = document.getElementById('countExc');
    const progressContainer = document.getElementById('progressContainer');
    const progressBar = document.getElementById('progressBar');
    const sourceUploads = document.getElementById('sourceUploads');
    const inclusionReasons = document.getElementById('inclusionReasons');
    const reportMetadata = document.getElementById('reportMetadata');
    const accessCard = document.getElementById('accessCard');
    const upgradeFlow = document.getElementById('upgradeFlow');
    const upgradeDetailsScreen = document.getElementById('upgradeDetailsScreen');
    const checkoutScreen = document.getElementById('checkoutScreen');
    const termsScreen = document.getElementById('termsScreen');
    const continueToCheckoutBtn = document.getElementById('continueToCheckoutBtn');
    const closeUpgradeBtn = document.getElementById('closeUpgradeBtn');
    const backToUpgradeDetailsBtn = document.getElementById('backToUpgradeDetailsBtn');
    const returnToResearchBtn = document.getElementById('returnToResearchBtn');
    const checkoutStatus = document.getElementById('checkoutStatus');
    const checkoutPlanName = document.getElementById('checkoutPlanName');
    const checkoutSourceCapacity = document.getElementById('checkoutSourceCapacity');
    const checkoutDomainCapacity = document.getElementById('checkoutDomainCapacity');
    const checkoutPlanPrice = document.getElementById('checkoutPlanPrice');
    const termsAgreement = document.getElementById('termsAgreement');
    const termsLinkBtn = document.getElementById('termsLinkBtn');
    const backToCheckoutBtn = document.getElementById('backToCheckoutBtn');
    const acceptTermsBtn = document.getElementById('acceptTermsBtn');
    const retryBtn = document.getElementById('retryBtn');
    const upgradeFromScanBtn = document.getElementById('upgradeFromScanBtn');
    const cancelScanBtn = document.getElementById('cancelScanBtn');
    const auditFilters = document.getElementById('auditFilters');
    const auditFilter = document.getElementById('auditFilter');
    const auditCompactNote = document.getElementById('auditCompactNote');
    const maxSourcesSelect = document.getElementById('max_sources');
    const domainSelect = document.getElementById('domain');
    const inclusionReasonsLabel = document.getElementById('inclusionReasonsLabel');
    const paypalUpgradeBtn = document.getElementById('paypalUpgradeBtn');
    const mpesaUpgradeBtn = document.getElementById('mpesaUpgradeBtn');
    const largeSourceInterestBtn = document.getElementById('largeSourceInterestBtn');
    const upgradeTile = document.getElementById('upgradeTile');
    const authGate = document.getElementById('authGate');
    const authPreviewSurface = document.getElementById('authPreviewSurface');
    const signupForm = document.getElementById('signupForm');
    const signupEmail = document.getElementById('signupEmail');
    const signupPassword = document.getElementById('signupPassword');
    const signupTerms = document.getElementById('signupTerms');
    const signupTermsScreen = document.getElementById('signupTermsScreen');
    const openSignupTermsBtn = document.getElementById('openSignupTermsBtn');
    const backToSignupBtn = document.getElementById('backToSignupBtn');
    const returnToSignupBtn = document.getElementById('returnToSignupBtn');
    const googleSignupBtn = document.getElementById('googleSignupBtn');
    const toggleAuthModeBtn = document.getElementById('toggleAuthModeBtn');
    const signOutBtn = document.getElementById('signOutBtn');
    const signedInText = document.getElementById('signedInText');
    const authIntro = document.getElementById('authIntro');
    const signupTermsLabel = signupTerms?.closest('.auth-terms');
    const authStatus = document.getElementById('authStatus');
    const signedInBadge = document.getElementById('signedInBadge');

    function showSignupTerms(showTerms) {
        if (authGate) authGate.style.display = showTerms ? 'none' : '';
        if (signupTermsScreen) signupTermsScreen.style.display = showTerms ? 'block' : 'none';
        if (showTerms) signupTermsScreen?.querySelector('button')?.focus();
    }

    openSignupTermsBtn?.addEventListener('click', () => showSignupTerms(true));
    backToSignupBtn?.addEventListener('click', () => showSignupTerms(false));
    returnToSignupBtn?.addEventListener('click', () => showSignupTerms(false));

    const step1 = document.getElementById('step1'); const step2 = document.getElementById('step2');
    const step3 = document.getElementById('step3'); const step4 = document.getElementById('step4');

    const postMvpReviewSection = document.getElementById('postMvpReviewSection');
    const synthesisFallbackCard = document.getElementById('synthesisFallbackCard');
    const draftDocBtn = document.getElementById('draftDocBtn');
    const fullDraftDocBtn = document.getElementById('fullDraftDocBtn');
    const proposalSpinner = document.getElementById('proposalSpinner');
    const fullPaperSpinner = document.getElementById('fullPaperSpinner');
    const draftBtnText = document.getElementById('draftBtnText');
    const fullDraftBtnText = document.getElementById('fullDraftBtnText');
    const cancelReportBtn = document.getElementById('cancelReportBtn');
    const retryReportBtn = document.getElementById('retryReportBtn');
    const draftStatus = document.getElementById('draftStatus');
    const downloadCachedReportBtn = document.getElementById('downloadCachedReportBtn');
    const upgradeFromReportBtn = document.getElementById('upgradeFromReportBtn');
    const sProgContainer = document.getElementById('scribeProgressContainer');
    const sProgressBar = document.getElementById('scribeProgressBar');
    const sStep1 = document.getElementById('sStep1'); const sStep2 = document.getElementById('sStep2');
    const sStep3 = document.getElementById('sStep3'); const sStep4 = document.getElementById('sStep4');

    const FREE_LIMIT = 5;
    const REPORT_CACHE_DB = 'nexus-report-cache';
    const REPORT_CACHE_STORE = 'reports';
    const REPORT_CACHE_TTL_MS = 30 * 24 * 60 * 60 * 1000;
    const REPORT_CACHE_MAX_BYTES = 8 * 1024 * 1024;
    let cachedReportKey = null;
    let currentReportCacheUserId = null;
    const DEFAULT_NEXUS_API_BASE_URL = 'https://nexus-os-production-2e14.up.railway.app';
    function createAnalyticsSessionId() {
        if (typeof crypto.randomUUID === 'function') return crypto.randomUUID();
        return Array.from(crypto.getRandomValues(new Uint8Array(16)),
            byte => byte.toString(16).padStart(2, '0')).join('');
    }
    const analyticsSessionId = createAnalyticsSessionId();

    async function getApiBaseUrl() {
        const configured = await chrome.storage.local.get(['nexus_api_base_url']);
        return (configured.nexus_api_base_url || DEFAULT_NEXUS_API_BASE_URL).replace(/\/+$/, '');
    }

    async function getApiHeaders() {
        const configured = await chrome.storage.local.get(['nexus_api_key']);
        const headers = {'Content-Type': 'application/json'};
        if (configured.nexus_api_key) headers['X-API-Key'] = configured.nexus_api_key;
        const session = await window.NexusAuth.getSession();
        if (session?.access_token) headers.Authorization = `Bearer ${session.access_token}`;
        return headers;
    }

    async function sendAnalytics(event, context = {}) {
        try {
            const storage = await chrome.storage.local.get(['nexus_auth_user']);
            if (!storage.nexus_auth_user) return;
            await fetch(`${await getApiBaseUrl()}/v1/analytics`, {
                method: 'POST',
                headers: await getApiHeaders(),
                body: JSON.stringify({
                    user_id: storage.nexus_auth_user?.email || 'anonymous',
                    session_id: analyticsSessionId,
                    source: 'extension',
                    event,
                    context
                })
            });
        } catch (error) {
            console.debug('[Nexus Analytics] event delivery skipped:', error.message);
        }
    }

    sendAnalytics('workspace_opened');

    const FEEDBACK_REASON_IDS = ['inaccurate', 'not_synthesized', 'citations', 'formatting', 'too_long', 'too_short'];
    let feedbackTarget = null;

    function hideFeedback() {
        feedbackTarget = null;
        const panel = document.getElementById('reportFeedback');
        if (panel) panel.style.display = 'none';
    }

    function offerFeedback(reference, reportType) {
        const panel = document.getElementById('reportFeedback');
        if (!panel || !reference) return hideFeedback();
        feedbackTarget = {reference, reportType};
        document.getElementById('feedbackPrompt').textContent = 'Was this report useful?';
        document.getElementById('feedbackChoices').style.display = 'flex';
        document.getElementById('feedbackReasons').style.display = 'none';
        FEEDBACK_REASON_IDS.forEach(id => { document.getElementById(`reason_${id}`).checked = false; });
        panel.style.display = 'block';
    }

    async function submitFeedback(rating) {
        if (!feedbackTarget) return;
        const target = feedbackTarget;
        const reasons = rating === 'down'
            ? FEEDBACK_REASON_IDS.filter(id => document.getElementById(`reason_${id}`).checked)
            : [];
        const prompt = document.getElementById('feedbackPrompt');
        try {
            const response = await fetch(`${await getApiBaseUrl()}/v1/feedback`, {
                method: 'POST',
                headers: await getApiHeaders(),
                body: JSON.stringify({
                    reference: target.reference, rating, reasons,
                    report_type: target.reportType === 'full_starter' ? 'full_starter' : 'proposal'
                })
            });
            if (!response.ok) throw new Error(`Feedback rejected (${response.status}).`);
        } catch (error) {
            prompt.textContent = 'Feedback could not be sent. You can try again.';
            return;
        }
        prompt.textContent = 'Thank you. Your feedback helps us improve the reports.';
        document.getElementById('feedbackChoices').style.display = 'none';
        document.getElementById('feedbackReasons').style.display = 'none';
        feedbackTarget = null;
    }

    document.getElementById('feedbackUp')?.addEventListener('click', () => submitFeedback('up'));
    document.getElementById('feedbackDown')?.addEventListener('click', () => {
        document.getElementById('feedbackChoices').style.display = 'none';
        document.getElementById('feedbackPrompt').textContent = 'What could be better? (optional)';
        document.getElementById('feedbackReasons').style.display = 'block';
    });
    document.getElementById('feedbackSend')?.addEventListener('click', () => submitFeedback('down'));

    let activeSessionIncludedPapers = [];
    let activeSessionExcludedPapers = [];
    let activeResearchRunId = null;
    let lastRequestContext = null;
    let activeReportButton = null;
    let activeReportType = null;
    let reportGenerationCancelled = false;
    let reportProcessingActive = false;
    const manifest = chrome.runtime.getManifest();
    const isLocalTestingInstall = !manifest.update_url;
    let isSignInMode = false;

    function setAuthStatus(message, type = 'error') {
        if (!authStatus) return;
        authStatus.textContent = message;
        authStatus.className = `auth-status ${type}`;
        authStatus.style.display = 'block';
    }

    function setSignedInState(user) {
        const signedIn = Boolean(user?.id && user?.email);
        currentReportCacheUserId = signedIn ? user.id : null;
        document.body.classList.toggle('auth-locked', !signedIn);
        if (authGate) authGate.hidden = signedIn;
        if (signupTermsScreen && signedIn) signupTermsScreen.style.display = 'none';
        if (authPreviewSurface) {
            authPreviewSurface.setAttribute('aria-hidden', String(!signedIn));
            authPreviewSurface.inert = !signedIn;
        }
        if (signedInBadge) {
            signedInBadge.style.display = signedIn ? 'block' : 'none';
            if (signedInText) signedInText.textContent = signedIn ? `Signed in as ${user.email}` : '';
        }
        loadCachedReportForUser(user?.id).catch(error =>
            console.debug('[Nexus Report Cache] cache lookup skipped:', error.message)
        );
    }

    async function loadAuthState() {
        try {
            const session = await window.NexusAuth.getSession();
            setSignedInState(session?.user);
        } catch (error) {
            setSignedInState(null);
            setAuthStatus(`Your session could not be refreshed: ${error.message}`);
        }
    }

    function setAuthMode(signIn) {
        isSignInMode = signIn;
        if (authGate) {
            const title = document.getElementById('authTitle');
            if (title) title.textContent = signIn ? 'Welcome back' : 'Create your research workspace';
        }
        if (authIntro) authIntro.textContent = signIn
            ? 'Sign in with your email and password to continue.'
            : 'Create an account or sign in to access your research workspace.';
        if (signupPassword) signupPassword.autocomplete = signIn ? 'current-password' : 'new-password';
        if (signupTermsLabel) signupTermsLabel.hidden = signIn;
        if (signupTerms) signupTerms.required = !signIn;
        const submitButton = document.getElementById('emailSignupBtn');
        if (submitButton) submitButton.textContent = signIn ? 'Sign in with email' : 'Create account with email';
        if (toggleAuthModeBtn) toggleAuthModeBtn.textContent = signIn
            ? 'Need an account? Sign up'
            : 'Already have an account? Sign in';
        if (authStatus) authStatus.style.display = 'none';
    }

    toggleAuthModeBtn?.addEventListener('click', () => setAuthMode(!isSignInMode));

    signupForm?.addEventListener('submit', async event => {
        event.preventDefault();
        const email = signupEmail?.value.trim().toLowerCase();
        const password = signupPassword?.value || '';
        if (!signupForm.checkValidity() || !email || (!isSignInMode && !signupTerms?.checked)) {
            setAuthStatus(isSignInMode
                ? 'Enter a valid email and password.'
                : 'Enter a valid email, use at least 8 characters for your password, and accept the terms.');
            signupForm.reportValidity();
            return;
        }
        const submitButton = document.getElementById('emailSignupBtn');
        if (submitButton) submitButton.disabled = true;
        try {
            if (isSignInMode) {
                const session = await window.NexusAuth.signIn(email, password);
                setSignedInState(session.user);
                setAuthStatus('You are signed in.', 'success');
            } else {
                const session = await window.NexusAuth.signUp(email, password);
                if (session) {
                    setSignedInState(session.user);
                    setAuthStatus('Account created. You are signed in.', 'success');
                } else {
                    setAuthStatus('Account created. Check your email to confirm your address, then sign in.', 'success');
                }
            }
        } catch (error) {
            setAuthStatus(error.message);
        } finally {
            if (submitButton) submitButton.disabled = false;
        }
    });

    googleSignupBtn?.addEventListener('click', async () => {
        googleSignupBtn.disabled = true;
        try {
            const session = await window.NexusAuth.signInWithGoogle();
            setSignedInState(session.user);
            setAuthStatus('Google sign-in succeeded.', 'success');
        } catch (error) {
            setAuthStatus(error.message);
        } finally {
            googleSignupBtn.disabled = false;
        }
    });

    signOutBtn?.addEventListener('click', async () => {
        signOutBtn.disabled = true;
        try {
            await window.NexusAuth.signOut();
            setSignedInState(null);
            setAuthStatus('You have signed out.', 'success');
        } catch (error) {
            setSignedInState(null);
            setAuthStatus(`Signed out on this device, but Supabase sign-out failed: ${error.message}`);
        } finally {
            signOutBtn.disabled = false;
        }
    });

    setAuthMode(false);
    loadAuthState();

    // Unpacked developer installs are whitelisted so local testing is not blocked.
    let isPaidUser = isLocalTestingInstall;

    const mainSurface = [
        banner,
        accessCard,
        document.querySelector('.tabs-nav'),
        ...document.querySelectorAll('.tab-content')
    ];

    // Prefilled with the reference id the user already sees; never an email address or personal data.
    function supportLink(reference) {
        const text = `Hi Nexus support, I need help with an error (reference ID ${String(reference || 'unknown').slice(0, 64)}).`;
        return `https://wa.me/254743852707?text=${encodeURIComponent(text)}`;
    }
    document.addEventListener('click', event => {
        if (event.target.closest('a[data-support]')) sendAnalytics('support_chat_clicked', {placement: 'extension'});
    });

    function showUpgradeFlow(screen = 'details') {
        mainSurface.forEach(element => {
            if (element) element.style.display = 'none';
        });
        if (upgradeFlow) upgradeFlow.style.display = 'block';
        if (upgradeDetailsScreen) upgradeDetailsScreen.style.display = screen === 'details' ? 'block' : 'none';
        if (checkoutScreen) checkoutScreen.style.display = screen === 'checkout' ? 'block' : 'none';
        if (termsScreen) termsScreen.style.display = screen === 'terms' ? 'block' : 'none';
    }

    function openUpgradeFlow(placement) {
        sendAnalytics('upgrade_cta_clicked', {placement});
        showUpgradeFlow('details');
    }

    function closeUpgradeFlow() {
        if (upgradeFlow) upgradeFlow.style.display = 'none';
        mainSurface.forEach(element => {
            if (element) element.style.display = '';
        });
    }

    let packs = [];
    let selectedPackId = null;

    function formatPackPrice(price) {
        const amount = Number(price);
        return Number.isInteger(amount) ? `$${amount}` : `$${amount.toFixed(2)}`;
    }

    function selectedPack() {
        return packs.find(pack => pack.id === selectedPackId) || packs[0] || null;
    }

    function renderCheckoutSummary() {
        const pack = selectedPack();
        if (!pack) return;
        if (checkoutPlanName) checkoutPlanName.textContent = pack.name;
        if (checkoutPlanPrice) checkoutPlanPrice.textContent = `${formatPackPrice(pack.price)} ${pack.currency} one-time`;
        if (checkoutSourceCapacity) checkoutSourceCapacity.textContent = `${pack.scans} scans`;
        if (checkoutDomainCapacity) checkoutDomainCapacity.textContent = `${pack.validity_days} days`;
        const terms = document.getElementById('termsPackPrice');
        if (terms) terms.textContent = `${pack.name} is a one-time purchase of ${formatPackPrice(pack.price)} ${pack.currency}. It does not renew.`;
    }

    function renderPackOptions() {
        const container = document.getElementById('packOptions');
        if (!container || !packs.length) return;
        container.replaceChildren(...packs.map((pack, index) => {
            const option = document.createElement('button');
            option.type = 'button';
            option.className = `plan-option${index === 0 ? ' selected' : ''}`;
            option.dataset.pack = pack.id;
            const name = Object.assign(document.createElement('strong'), {textContent: pack.name});
            const detail = Object.assign(document.createElement('span'), {
                textContent: `${pack.scans} scans, full Excel and Word downloads, ${pack.validity_days} days.`,
            });
            const price = Object.assign(document.createElement('span'), {
                className: 'plan-price',
                textContent: `${formatPackPrice(pack.price)} one-time`,
            });
            const perScan = Object.assign(document.createElement('span'), {
                className: 'plan-action', textContent: `Just $${pack.per_scan} per scan${pack.badge ? ` · ${pack.badge}` : ''}`,
            });
            option.append(name, detail, price, perScan);
            return option;
        }));
    }

    async function loadPackInfo() {
        if (packs.length) return packs;
        try {
            const response = await fetch(`${await getApiBaseUrl()}/v1/checkout/packs`);
            if (!response.ok) return null;
            const catalog = await response.json();
            packs = Array.isArray(catalog.packs) ? catalog.packs : [];
            selectedPackId = catalog.default || packs[0]?.id || null;
        } catch (error) {
            return null;
        }
        renderPackOptions();
        renderCheckoutSummary();
        return packs;
    }

    upgradeTile?.addEventListener('click', () => openUpgradeFlow('extension_tile'));
    upgradeTile?.addEventListener('keydown', event => {
        if (event.key === 'Enter' || event.key === ' ') openUpgradeFlow('extension_tile');
    });
    banner?.addEventListener('click', () => openUpgradeFlow('extension_banner'));
    banner?.addEventListener('keydown', event => {
        if (event.key === 'Enter' || event.key === ' ') openUpgradeFlow('extension_banner');
    });
    continueToCheckoutBtn?.addEventListener('click', () => showUpgradeFlow('checkout'));
    closeUpgradeBtn?.addEventListener('click', closeUpgradeFlow);
    backToUpgradeDetailsBtn?.addEventListener('click', () => showUpgradeFlow('details'));
    returnToResearchBtn?.addEventListener('click', closeUpgradeFlow);
    document.getElementById('packOptions')?.addEventListener('click', event => {
        const option = event.target.closest('button[data-pack]');
        if (!option) return;
        selectedPackId = option.dataset.pack;
        renderCheckoutSummary();
        showUpgradeFlow('checkout');
    });
    termsLinkBtn?.addEventListener('click', () => showUpgradeFlow('terms'));
    backToCheckoutBtn?.addEventListener('click', () => showUpgradeFlow('checkout'));
    acceptTermsBtn?.addEventListener('click', () => {
        if (termsAgreement) termsAgreement.checked = true;
        showUpgradeFlow('checkout');
    });
    loadPackInfo();

    async function refreshEntitlements() {
        const storage = await chrome.storage.local.get(["nexus_auth_user"]);
        const userId = storage.nexus_auth_user?.email;
        let serverActive = false;
        if (userId) {
            try {
                const response = await fetch(
                    `${await getApiBaseUrl()}/v1/entitlements/${encodeURIComponent(userId)}`,
                    {headers: await getApiHeaders()}
                );
                if (response.ok) serverActive = Boolean((await response.json()).active);
            } catch (error) {
                console.debug('[Nexus Entitlements] refresh skipped:', error.message);
            }
        }
        isPaidUser = serverActive || isLocalTestingInstall;
        if (inclusionReasonsLabel) inclusionReasonsLabel.textContent =
            `Inclusion reasons (select up to ${isPaidUser ? 5 : 3}; defaults apply if none selected)`;
        if (maxSourcesSelect) {
            [...maxSourcesSelect.options].forEach(option => {
                if (option.classList.contains('paid-only-source-option')) option.disabled = !isPaidUser;
                if (option.classList.contains('premium-source-option')) option.disabled = true;
            });
            if (!isPaidUser && Number(maxSourcesSelect.value) > 20) maxSourcesSelect.value = "20";
        }
        if (domainSelect) {
            const legal = domainSelect.querySelector('.paid-only-domain-option');
            if (legal) legal.disabled = !isPaidUser;
            if (!isPaidUser && domainSelect.value === 'legal') domainSelect.value = 'scholarly';
        }
        const checked = inclusionReasons?.querySelectorAll('input:checked') || [];
        if (!checked.length && inclusionReasons) {
            const defaults = [...inclusionReasons.querySelectorAll('input')];
            defaults.forEach((input, index) => {
                input.checked = isPaidUser || index < 3;
            });
        }
    }
    refreshEntitlements();

    function extractErrorMessage(payload, status) {
        if (!payload) return `Request failed (${status || 'unknown'}).`;
        if (typeof payload === 'string') return payload;
        if (typeof payload.detail === 'string') return payload.detail;
        if (payload.detail && typeof payload.detail === 'object') {
            if (Array.isArray(payload.detail)) {
                const msgs = payload.detail.map(d => (d && typeof d === 'object') ? (d.msg || d.message || JSON.stringify(d)) : String(d)).filter(Boolean);
                if (msgs.length) return msgs.join(', ');
            } else if (payload.detail.message) {
                return String(payload.detail.message);
            } else if (payload.detail.detail) {
                return String(payload.detail.detail);
            }
        }
        if (typeof payload.message === 'string') return payload.message;
        if (typeof payload.error === 'string') return payload.error;
        if (typeof payload === 'object') {
            if (payload.message && typeof payload.message === 'object') {
                return extractErrorMessage(payload.message, status);
            }
        }
        try {
            return JSON.stringify(payload);
        } catch (_) {
            return `Request failed (${status || 'unknown'}).`;
        }
    }

    async function fetchBinaryReport(url) {
        const fullUrl = url.startsWith('http') ? url : `${await getApiBaseUrl()}${url}`;
        const response = await fetch(fullUrl, {
            method: 'GET',
            headers: await getApiHeaders()
        });
        if (!response.ok) {
            const errJson = await response.json().catch(() => ({}));
            throw new Error(extractErrorMessage(errJson, response.status) || `Download failed (${response.status})`);
        }
        return await response.blob();
    }

    async function pollReportJobStatus(jobId, reportType) {
        const maxAttempts = 60;
        const intervalMs = 2500;
        const baseUrl = await getApiBaseUrl();

        for (let attempt = 0; attempt < maxAttempts; attempt++) {
            await new Promise(resolve => setTimeout(resolve, intervalMs));
            
            const response = await fetch(`${baseUrl}/v1/reports/${encodeURIComponent(jobId)}/status`, {
                headers: await getApiHeaders()
            });
            if (!response.ok) {
                const errJson = await response.json().catch(() => ({}));
                throw new Error(extractErrorMessage(errJson, response.status) || 'Status check failed.');
            }

            const job = await response.json();

            if (job.status === 'completed' || job.status === 'ready') {
                const downloadUrl = job.download_url || `/v1/reports/${encodeURIComponent(jobId)}/download`;
                const filename = job.document_name || `${reportType}-report.docx`;
                const blob = await fetchBinaryReport(downloadUrl);
                return { blob, filename, job };
            }

            if (job.status === 'failed') {
                const err = new Error(job.error_message || job.error_reason || 'Report generation could not be completed.');
                err.jobId = jobId;
                throw err;
            }

            if (sProgressBar) {
                const pct = Math.min(95, 30 + Math.floor((attempt / maxAttempts) * 65));
                sProgressBar.style.width = `${pct}%`;
            }
        }

        const timeoutErr = new Error('Report synthesis timed out. Request is queued.');
        timeoutErr.jobId = jobId;
        throw timeoutErr;
    }

    let currentRoutingSessionToken = "idle";
    async function sendBackgroundRequest(request) {
        const isReport = request.action === 'trigger_docx_generation';
        const endpoint = isReport ? '/v1/reports' : '/v1/scan';
        const payload = isReport
            ? {
                topic: request.topic,
                included_sources: request.included_sources || [],
                ...(request.research_run_id ? {research_run_id: request.research_run_id} : {}),
                ...(request.preview ? {preview: true} : {}),
                uploaded_sources: request.uploaded_sources || [],
                report_type: request.report_type || 'proposal',
                domain: request.domain || 'scholarly',
                max_sources: Number(request.max_sources || 5)
            }
            : {
                topic: request.topic,
                max_sources: Number(request.max_sources || 5),
                domain: request.domain || 'scholarly',
                uploaded_sources: request.uploaded_sources || [],
                selected_inclusion_reasons: request.selected_inclusion_reasons || []
            };
        try {
            const response = await fetch(`${await getApiBaseUrl()}${endpoint}`, {
                method: 'POST',
                headers: await getApiHeaders(),
                body: JSON.stringify(payload)
            });
            const data = await response.json().catch(() => ({}));
            if (!response.ok) {
                const message = extractErrorMessage(data, response.status);
                const requestError = new Error(message);
                requestError.status = response.status;
                requestError.payload = data;
                throw requestError;
            }
            if (!data || typeof data !== 'object' || Array.isArray(data)) {
                throw new Error('The research API returned an invalid response.');
            }
            if (isReport) {
                // Support queued, immediate base64, direct download URL, or cache ID
                if (data.status === 'queued' || data.action === 'report_queued_pending') {
                    data.action = 'report_queued_pending';
                    data.status = 'queued';
                } else {
                    data.action = data.action || (data.document_base64 || data.download_url || data.report_cache_id ? 'docx_generation_complete' : 'report_queued_pending');
                }
            } else {
                if (!Array.isArray(data.included)) {
                    throw new Error('The research API returned an incomplete scan result.');
                }
                data.status = data.status || 'success';
                data.action = 'research_scan_complete';
                data.excluded = data.excluded || [];
            }
            await handleBackgroundResponse({success: true, data});
            return {success: true, data};
        } catch (error) {
            const errorDetail = (error.payload && error.payload.detail) || error.payload || {};
            const data = {
                status: 'error',
                message: error.message,
                status_code: error.status,
                error_code: errorDetail.error_code,
                retryable: errorDetail.retryable,
                retry_after_seconds: errorDetail.retry_after_seconds
            };
            await handleBackgroundResponse({success: true, data});
            return {success: false, data};
        }
    }

    function createReportBlob(encodedReport) {
        if (!encodedReport || typeof encodedReport !== 'string') {
            throw new Error('Report document data is not available.');
        }
        // Strip any whitespace, newlines, or data URI prefix if present
        let cleanBase64 = encodedReport.trim();
        if (cleanBase64.includes(',')) {
            cleanBase64 = cleanBase64.split(',')[1];
        }
        cleanBase64 = cleanBase64.replace(/\s+/g, '');
        // Pad with = if length % 4 != 0
        while (cleanBase64.length % 4 !== 0) {
            cleanBase64 += '=';
        }
        try {
            const binary = atob(cleanBase64);
            const bytes = new Uint8Array(binary.length);
            for (let index = 0; index < binary.length; index++) {
                bytes[index] = binary.charCodeAt(index);
            }
            return new Blob(
                [bytes],
                {type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'}
            );
        } catch (error) {
            throw new Error('The generated report document could not be decoded.');
        }
    }

    function downloadReportBlob(reportBlob, filename) {
        const reportUrl = URL.createObjectURL(reportBlob);
        const link = document.createElement('a');
        link.href = reportUrl;
        link.download = filename;
        link.click();
        setTimeout(() => URL.revokeObjectURL(reportUrl), 60_000);
    }

    function openReportCache() {
        return new Promise((resolve, reject) => {
            const request = indexedDB.open(REPORT_CACHE_DB, 1);
            request.onupgradeneeded = () => {
                const database = request.result;
                if (!database.objectStoreNames.contains(REPORT_CACHE_STORE)) {
                    database.createObjectStore(REPORT_CACHE_STORE, {keyPath: 'key'});
                }
            };
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error || new Error('Could not open report cache.'));
        });
    }

    async function getCachedReports() {
        const database = await openReportCache();
        return new Promise((resolve, reject) => {
            const transaction = database.transaction(REPORT_CACHE_STORE, 'readonly');
            const request = transaction.objectStore(REPORT_CACHE_STORE).getAll();
            request.onsuccess = () => resolve(request.result || []);
            request.onerror = () => reject(request.error || new Error('Could not read cached reports.'));
            transaction.oncomplete = () => database.close();
            transaction.onerror = () => {
                database.close();
                reject(transaction.error || new Error('Could not read cached reports.'));
            };
        });
    }

    async function cacheGeneratedReport(reportBlob, reportName, reportType, reportTopic, userId) {
        if (!userId || reportBlob.size > REPORT_CACHE_MAX_BYTES) return false;
        const database = await openReportCache();
        const cacheKey = `${userId}:${reportType}`;
        return new Promise((resolve, reject) => {
            const transaction = database.transaction(REPORT_CACHE_STORE, 'readwrite');
            const store = transaction.objectStore(REPORT_CACHE_STORE);
            const existingRequest = store.getAll();
            existingRequest.onsuccess = () => {
                const now = Date.now();
                existingRequest.result.forEach(report => {
                    if (report.userId !== userId || report.expiresAt <= now) {
                        store.delete(report.key);
                    }
                });
                store.put({
                    key: cacheKey,
                    userId,
                    reportType,
                    reportTopic,
                    reportName,
                    reportBlob,
                    createdAt: now,
                    expiresAt: now + REPORT_CACHE_TTL_MS
                });
            };
            existingRequest.onerror = () => transaction.abort();
            transaction.oncomplete = () => {
                database.close();
                resolve(true);
            };
            transaction.onerror = () => {
                database.close();
                reject(transaction.error || new Error('Could not save report to cache.'));
            };
            transaction.onabort = () => {
                database.close();
                reject(transaction.error || new Error('Report cache write was aborted.'));
            };
        });
    }

    async function loadCachedReportForUser(userId) {
        cachedReportKey = null;
        if (downloadCachedReportBtn) downloadCachedReportBtn.style.display = 'none';
        if (!userId || !window.indexedDB) return;
        const reports = await getCachedReports();
        if (currentReportCacheUserId !== userId) return;
        const now = Date.now();
        const validReports = reports.filter(report =>
            report.userId === userId && report.expiresAt > now
        );
        const expiredReports = reports.filter(report => report.expiresAt <= now);
        if (expiredReports.length) {
            const database = await openReportCache();
            const transaction = database.transaction(REPORT_CACHE_STORE, 'readwrite');
            const store = transaction.objectStore(REPORT_CACHE_STORE);
            expiredReports.forEach(report => store.delete(report.key));
            transaction.oncomplete = () => database.close();
            transaction.onerror = () => database.close();
        }
        const latest = validReports.sort((left, right) => right.createdAt - left.createdAt)[0];
        if (!latest) return;
        cachedReportKey = latest.key;
        if (downloadCachedReportBtn) {
            const reportKind = latest.reportType === 'full_starter' ? 'complete literature review' : 'proposal';
            downloadCachedReportBtn.textContent = `Download cached ${reportKind}: ${latest.reportTopic}`;
            downloadCachedReportBtn.style.display = 'block';
        }
    }

    downloadCachedReportBtn?.addEventListener('click', async () => {
        try {
            const session = await window.NexusAuth.getSession();
            if (!session?.user?.id || !cachedReportKey) {
                throw new Error('Sign in to the account that generated this report.');
            }
            const database = await openReportCache();
            const report = await new Promise((resolve, reject) => {
                const transaction = database.transaction(REPORT_CACHE_STORE, 'readonly');
                const request = transaction.objectStore(REPORT_CACHE_STORE).get(cachedReportKey);
                request.onsuccess = () => resolve(request.result);
                request.onerror = () => reject(request.error || new Error('Could not read cached report.'));
                transaction.oncomplete = () => database.close();
                transaction.onerror = () => {
                    database.close();
                    reject(transaction.error || new Error('Could not read cached report.'));
                };
            });
            if (!report || report.userId !== session.user.id || report.expiresAt <= Date.now()) {
                throw new Error('This cached report is no longer available. Generate it again to download a fresh copy.');
            }
            downloadReportBlob(report.reportBlob, report.reportName);
            if (draftStatus) {
                draftStatus.className = 'success';
                draftStatus.textContent = `Downloaded cached report: ${report.reportName}`;
                draftStatus.style.display = 'block';
            }
        } catch (error) {
            if (draftStatus) {
                draftStatus.className = 'error';
                draftStatus.textContent = error.message;
                draftStatus.style.display = 'block';
            }
        }
    });

    upgradeFromReportBtn?.addEventListener('click', () => openUpgradeFlow('extension_report'));
    upgradeFromScanBtn?.addEventListener('click', () => openUpgradeFlow('extension_scan_limit'));

    function markStep(stepElement, state) {
        if (!stepElement) return; const iconSpan = stepElement.querySelector('.step-icon');
        if (state === 'active') { stepElement.className = 'step-item active'; if (iconSpan) iconSpan.innerText = '🔵'; }
        else if (state === 'success') { stepElement.className = 'step-item completed'; if (iconSpan) iconSpan.innerText = '✅'; }
        else if (state === 'fail') { stepElement.className = 'step-item failed'; if (iconSpan) iconSpan.innerText = '❌'; }
    }

    async function updateTierUI() {
        if (isLocalTestingInstall) {
            if (banner) banner.innerHTML = '<span>🧪 <strong>Nexus Research AI Local Testing</strong> (scan limits bypassed)</span>';
            return;
        }
        const data = await chrome.storage.local.get(["usage_count"]); const count = data.usage_count || 0;
        const remaining = Math.max(0, FREE_LIMIT - count);
        if (banner) banner.innerHTML = `<span>💎 <strong>Nexus Research AI Freemium Tier</strong> (${remaining}/${FREE_LIMIT} checks left)</span>`;
    }
    updateTierUI();

    async function readUploads() {
        if (!sourceUploads || !sourceUploads.files.length) return [];
        return Promise.all([...sourceUploads.files].map(file => new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve({
                name: file.name,
                type: file.type,
                data: String(reader.result).split(',')[1] || ''
            });
            reader.onerror = () => reject(reader.error || new Error(`Could not read ${file.name}`));
            reader.readAsDataURL(file);
        })));
    }

    function readInclusionReasons() {
        const selected = [...(inclusionReasons?.querySelectorAll('input:checked') || [])]
            .map(input => input.value);
        return selected.slice(0, isPaidUser ? 5 : 3);
    }

    inclusionReasons?.addEventListener('change', (event) => {
        const checked = inclusionReasons.querySelectorAll('input:checked');
        if (checked.length > (isPaidUser ? 5 : 3)) event.target.checked = false;
    });

    function renderAuditRows() {
        if (!auditTableBody) return;
        const filter = auditFilter?.value || 'all';
        auditTableBody.innerHTML = "";
        const rows = [];
        if (filter !== 'skipped') rows.push(...activeSessionIncludedPapers.map(item => ({item, passed: true})));
        if (filter !== 'passed') rows.push(...activeSessionExcludedPapers.map(item => ({item, passed: false})));
        const compact = rows.length > 20;
        const visibleRows = compact ? rows.slice(0, 20) : rows;
        visibleRows.forEach(({item, passed}) => {
            const row = document.createElement('tr');
            row.innerHTML = passed
                ? `<td><strong>${item.title || 'Untitled'}</strong></td><td><span class="badge badge-inc">PASSED</span></td><td>Verified. ${item.citation_count || 0} citations.</td>`
                : `<td>${item.title || 'Filtered'}</td><td><span class="badge badge-exc">SKIP</span></td><td>${item.exclusion_reason || 'Below precision baseline floor.'}</td>`;
            auditTableBody.appendChild(row);
        });
        if (auditCompactNote) auditCompactNote.textContent = compact
            ? `Showing 20 of ${rows.length} records. Use the filter or Excel dossier for the complete audit.`
            : `${rows.length} records in this view.`;
    }
    auditFilter?.addEventListener('change', renderAuditRows);

    async function trackInterest(eventName, message) {
        const key = `interest_${eventName}`;
        const current = await chrome.storage.local.get([key]);
        await chrome.storage.local.set({ [key]: (current[key] || 0) + 1 });
        const destination = checkoutStatus || statusDiv;
        if (destination) {
            destination.className = 'success';
            destination.innerText = message;
            destination.style.display = 'block';
        }
    }
    paypalUpgradeBtn?.addEventListener('click', async () => {
        if (!termsAgreement?.checked) {
            if (checkoutStatus) {
                checkoutStatus.className = 'error';
                checkoutStatus.innerText = 'Please review and accept the payment and refund terms first.';
                checkoutStatus.style.display = 'block';
            }
            return;
        }
        const destination = checkoutStatus || statusDiv;
        if (destination) {
            destination.className = 'success';
            destination.innerText = 'Preparing secure PayPal checkout...';
            destination.style.display = 'block';
        }
        try {
            const response = await fetch(`${await getApiBaseUrl()}/v1/checkout/orders`, {
                method: 'POST',
                headers: await getApiHeaders(),
                body: JSON.stringify({pack_id: selectedPack()?.id || null})
            });
            if (!response.ok) {
                const failure = await response.json().catch(() => ({}));
                throw new Error(failure.detail?.message || `Checkout request failed (${response.status}).`);
            }
            const order = await response.json();
            if (!order.approve_url) throw new Error('PayPal did not return an approval URL.');
            sendAnalytics('paypal_approval_opened', {plan: order.pack?.id || 'pack', order_id: order.order_id});
            chrome.tabs.create({url: order.approve_url});
            if (destination) destination.innerText = 'PayPal checkout opened in a new tab.';
        } catch (error) {
            sendAnalytics('payment_failed', {
                provider: 'paypal',
                error_code: 'CLIENT_CHECKOUT_ERROR'
            });
            if (destination) {
                destination.className = 'error';
                destination.innerText = `PayPal checkout could not start: ${error.message}`;
            }
        }
    });
    mpesaUpgradeBtn?.addEventListener('click', () =>
        trackInterest('mpesa_interest_clicks', 'M-PESA support is being evaluated. We recorded your interest.')
    );
    largeSourceInterestBtn?.addEventListener('click', () =>
        trackInterest('large_source_pack_clicks', 'We recorded your interest in larger source packs.')
    );
// extension/popup.js - Fragment 2 of 2 (Session Isolation & Event Triggers)
    // Free users get one proposal snapshot a month: the outline and opening paragraph, never the document.
    // Everything from the server is shown as text; the locked sections are only names and word counts.
    function renderProposalSnapshot(snapshot) {
        if (!draftStatus) return;
        const box = document.createElement('div');
        box.className = 'snapshot-box';
        const title = document.createElement('strong');
        title.textContent = 'Proposal preview (free)';
        box.append(title);
        if (snapshot.opening_paragraph) {
            const opening = document.createElement('p');
            opening.className = 'snapshot-opening';
            opening.textContent = snapshot.opening_paragraph;
            box.append(opening);
        }
        const outline = document.createElement('ul');
        outline.className = 'snapshot-outline';
        (snapshot.sections || []).forEach((section, index) => {
            const item = document.createElement('li');
            item.textContent = `${index === 0 ? '' : '🔒 '}${section.title} · ${section.words} words`;
            outline.append(item);
        });
        box.append(outline);
        const counts = document.createElement('p');
        counts.className = 'snapshot-counts';
        counts.textContent = `${snapshot.citation_count} citations · ${snapshot.reference_count} references · ${snapshot.locked_sections} sections locked`;
        box.append(counts);
        const unlock = document.createElement('button');
        unlock.type = 'button';
        unlock.className = 'btn';
        unlock.textContent = 'Unlock the full proposal';
        unlock.addEventListener('click', () => openUpgradeFlow('extension_snapshot'));
        box.append(unlock);
        draftStatus.className = '';
        draftStatus.replaceChildren(box);
        draftStatus.style.display = 'block';
    }

    async function handleBackgroundResponse(response) {
        if (!response || !response.success || !response.data) {
            reportProcessingActive = false;
            resetScribeButtonState();
            runButton.disabled = false;
            if (btnSpinner) btnSpinner.style.display = 'none';
            if (btnText) btnText.innerText = 'Launch Research Agents';
            if (progressContainer) progressContainer.style.display = 'none';
            if (cancelScanBtn) cancelScanBtn.style.display = 'none';
            currentRoutingSessionToken = "idle";
            if (statusDiv) {
                statusDiv.className = 'error';
                statusDiv.innerText = `Processing failed: ${response?.data?.message || response?.error || 'The host returned an unknown error.'}`;
                statusDiv.style.display = 'block';
            }
            if (retryBtn && lastRequestContext?.action === 'trigger_nexus_scan') retryBtn.style.display = 'block';
            if (retryReportBtn && lastRequestContext?.action === 'trigger_docx_generation') retryReportBtn.style.display = 'block';
            sendAnalytics('error_displayed', {
                surface: lastRequestContext?.action === 'trigger_docx_generation' ? 'report' : 'scan',
                error_code: 'host_error'
            });
            return;
        }

        const data = response.data;
        if (data.status === 'error') {
            reportProcessingActive = false;
            const isReportRequest = lastRequestContext?.action === 'trigger_docx_generation';
            const message = (data.message && typeof data.message === 'object')
                ? extractErrorMessage(data.message, data.status_code || 500)
                : (data.message || 'Processing failed.');
            const referenceId = data.job_id || data.run_id || (lastRequestContext?.topic ? Math.random().toString(36).substring(2, 10) : 'nexus_err');
            
            if (isReportRequest && draftStatus) {
                const errorCode = data.error_code || (data.status_code === 403 ? 'paywall' : 'unknown');

                let errorTitle = "Report could not be generated";
                let errorMsg = "The report generation service encountered an issue. Your Excel dossier was completed successfully.";
                let bgColor = '#fee';
                let borderColor = '#dc2626';
                let textColor = '#991b1b';
                let accentColor = '#7f1d1d';

                if (errorCode === 'quota_daily') {
                    errorTitle = "Daily quota reached";
                    errorMsg = "The synthesis service has reached its daily limit. Please try again tomorrow.";
                    bgColor = '#fef3c7';
                    borderColor = '#f59e0b';
                    textColor = '#92400e';
                    accentColor = '#78350f';
                } else if (errorCode === 'unavailable') {
                    errorTitle = "Service temporarily busy";
                    errorMsg = "The report service is at capacity. Try again in a few minutes.";
                    bgColor = '#fef3c7';
                    borderColor = '#f59e0b';
                    textColor = '#92400e';
                    accentColor = '#78350f';
                } else if (errorCode === 'upgrade_required') {
                    errorTitle = "Unlock the full Word proposal";
                    errorMsg = "The full Word proposal is included with a Research Pack. Your results and the Excel audit summary stay available here.";
                    bgColor = '#dbeafe';
                    borderColor = '#3b82f6';
                    textColor = '#1e3a8a';
                    accentColor = '#1e40af';
                } else if (errorCode === 'paywall') {
                    errorTitle = "Premium feature";
                    errorMsg = "Complete Literature Review is available to paid users. Upgrade to access.";
                    bgColor = '#dbeafe';
                    borderColor = '#3b82f6';
                    textColor = '#1e3a8a';
                    accentColor = '#1e40af';
                }

                draftStatus.className = 'error';
                draftStatus.innerHTML = `
                    <div style="padding: 10px; border-radius: 3px; background: ${bgColor}; border-left: 4px solid ${borderColor};">
                        <div style="font-weight: 600; color: ${textColor}; margin-bottom: 4px;">${errorTitle}</div>
                        <div style="color: ${accentColor}; font-size: 0.9em; margin-bottom: 8px;">${errorMsg}</div>
                        <div style="font-size: 0.8em; color: ${accentColor};">Ref: <code style="background: rgba(0,0,0,0.1); padding: 1px 3px; border-radius: 2px;">${referenceId}</code></div>
                        <a data-support="extension" href="${supportLink(referenceId)}" target="_blank" rel="noopener noreferrer" style="display: inline-block; margin-top: 6px; font-size: 0.85em; color: ${accentColor}; font-weight: 600;">Chat with support on WhatsApp</a>
                    </div>
                `;
                draftStatus.style.display = 'block';
                if (upgradeFromReportBtn) {
                    upgradeFromReportBtn.style.display = data.status_code === 403 ? 'block' : 'none';
                }
            } else if (statusDiv) {
                statusDiv.className = 'error';
                statusDiv.innerText = message;
                statusDiv.style.display = 'block';
                if (upgradeFromScanBtn) upgradeFromScanBtn.style.display = data.status_code === 403 ? 'block' : 'none';
            }
            resetScribeButtonState();
            if (activeReportButton) activeReportButton.disabled = false;
            if (cancelScanBtn) cancelScanBtn.style.display = 'none';
            if (retryBtn && lastRequestContext?.action === 'trigger_nexus_scan') retryBtn.style.display = 'block';
            if (retryReportBtn) {
                retryReportBtn.style.display = 'none';
            }
            if (cancelReportBtn) cancelReportBtn.style.display = 'none';
            if (sProgContainer) sProgContainer.style.display = 'none';
            sendAnalytics('error_displayed', {
                surface: isReportRequest ? 'report' : 'scan',
                error_code: 'api_error',
                status_code: data.status_code || null,
                reference_id: referenceId
            });
            currentRoutingSessionToken = "idle";
            return;
        }

        if (data.status === 'snapshot' && data.snapshot) {
            reportProcessingActive = false;
            resetScribeButtonState();
            if (activeReportButton) activeReportButton.disabled = false;
            if (sProgContainer) sProgContainer.style.display = 'none';
            if (cancelReportBtn) cancelReportBtn.style.display = 'none';
            if (retryReportBtn) retryReportBtn.style.display = 'none';
            renderProposalSnapshot(data.snapshot);
            currentRoutingSessionToken = 'idle';
            return;
        }

        // Keep the report controls alive for any non-terminal host response.
        // Only a saved document, queued status, or an explicit error should end report processing.
        if (reportProcessingActive &&
            data.action !== 'docx_generation_complete' &&
            data.action !== 'report_queued_pending' &&
            data.status !== 'queued' &&
            !data.document_saved_at &&
            currentRoutingSessionToken === 'docx_generation_active') {
            return;
        }

        // --- PRODUCTION LOGIC VECTOR A: INTERCEPT CITATION DOCUMENT SCRIBE WRITES & QUEUES ---
        // Handle queued report synthesis or asynchronous jobs
        const isQueuedReport = (
            data.status === 'queued' ||
            data.action === 'report_queued_pending' ||
            (!data.document_base64 && !data.document_saved_at && !data.download_url && (data.job_id || data.report_id || data.id))
        );

        if ((currentRoutingSessionToken === "docx_generation_active" || lastRequestContext?.action === 'trigger_docx_generation') && isQueuedReport) {
            const jobId = data.job_id || data.report_id || data.id;
            if (jobId) {
                if (draftStatus) {
                    const isPaid = data.is_paid === true;
                    let queuedMessage = data.message || `Report synthesis request queued (${data.estimated_wait || 'usually under 20 minutes'}).`;

                    if (isPaid) {
                        queuedMessage = `Your report is in the priority lane. The writing service is busy, so we saved your request and will retry with priority. Your Excel dossier is ready now. (${data.estimated_wait || 'usually under 20 minutes'})`;
                    } else {
                        queuedMessage = `Your report is in the queue. The writing service is busy, so we saved your request and will retry automatically. Your Excel dossier is ready now. (${data.estimated_wait || 'usually under 20 minutes'}). Upgrade to skip the line.`;
                    }

                    draftStatus.className = 'info';
                    draftStatus.textContent = queuedMessage;
                    draftStatus.style.display = 'block';

                    if (upgradeFromReportBtn && !isPaid) {
                        upgradeFromReportBtn.style.display = 'block';
                    }
                }
                try {
                    const { blob, filename, job } = await pollReportJobStatus(jobId, activeReportType);
                    downloadReportBlob(blob, filename);
                    
                    try {
                        const session = await window.NexusAuth.getSession();
                        await cacheGeneratedReport(
                            blob,
                            filename,
                            activeReportType,
                            lastRequestContext?.topic || '',
                            session?.user?.id
                        );
                        await loadCachedReportForUser(session?.user?.id);
                    } catch (_) {}

                    resetScribeButtonState();
                    if (activeReportButton) activeReportButton.disabled = false;
                    currentRoutingSessionToken = "idle";
                    if (sProgContainer) sProgContainer.style.display = 'none';
                    if (draftStatus) {
                        draftStatus.className = 'success';
                        draftStatus.textContent = `Project writeup compiled successfully. Downloaded: ${filename}`;
                        draftStatus.style.display = 'block';
                    }
                    return;
                } catch (pollErr) {
                    reportProcessingActive = false;
                    resetScribeButtonState();
                    if (activeReportButton) activeReportButton.disabled = false;
                    if (sProgContainer) sProgContainer.style.display = 'none';
                    if (cancelReportBtn) cancelReportBtn.style.display = 'none';
                    if (draftStatus) {
                        draftStatus.className = 'info';
                        draftStatus.textContent = data.message || `Report synthesis request queued (${data.estimated_wait || 'usually under 20 minutes'}).`;
                        draftStatus.style.display = 'block';
                    }
                    currentRoutingSessionToken = 'idle';
                    return;
                }
            } else {
                reportProcessingActive = false;
                resetScribeButtonState();
                if (activeReportButton) activeReportButton.disabled = false;
                if (sProgContainer) sProgContainer.style.display = 'none';
                if (cancelReportBtn) cancelReportBtn.style.display = 'none';
                if (draftStatus) {
                    draftStatus.className = 'info';
                    draftStatus.textContent = data.message || `Report synthesis request queued (${data.estimated_wait || 'usually under 20 minutes'}).`;
                    draftStatus.style.display = 'block';
                }
                currentRoutingSessionToken = 'idle';
                return;
            }
        }

        // Only allow document download if ready / completed and document payload exists
        const isDocxReady = (
            data.status === 'ready' ||
            data.status === 'completed' ||
            data.action === "docx_generation_complete" ||
            data.document_saved_at ||
            data.download_url ||
            (data.document_base64 && typeof data.document_base64 === 'string')
        );

        if ((currentRoutingSessionToken === "docx_generation_active" || data.action === "docx_generation_complete") && isDocxReady) {
            if (reportGenerationCancelled) return;
            reportProcessingActive = false;
            let reportBlob;
            let cacheSaved = false;
            const docName = data.document_name || `${activeReportType}-report.docx`;
            try {
                if (data.download_url) {
                    reportBlob = await fetchBinaryReport(data.download_url);
                } else if (data.report_cache_id) {
                    reportBlob = await fetchBinaryReport(`/v1/reports/cache/${encodeURIComponent(data.report_cache_id)}/download?report_type=${encodeURIComponent(activeReportType)}`);
                } else if (data.document_base64) {
                    reportBlob = createReportBlob(data.document_base64);
                } else {
                    throw new Error('Report document content not returned.');
                }
                downloadReportBlob(reportBlob, docName);
            } catch (error) {
                resetScribeButtonState();
                if (activeReportButton) activeReportButton.disabled = false;
                if (sProgContainer) sProgContainer.style.display = 'none';
                if (draftStatus) {
                    const referenceId = data.job_id || (lastRequestContext?.topic ? Math.random().toString(36).substring(2, 10) : 'nexus_err');
                    draftStatus.className = 'error';
                    draftStatus.innerHTML = `
                        <div>
                            <strong>Report generation couldn't be completed.</strong>
                            <div style="margin: 4px 0;">We generated your Excel dossier successfully, but the report couldn't be completed this time.</div>
                            <div style="font-size: 0.85em; opacity: 0.85;">Reference: <code>${referenceId}</code></div>
                        </div>
                    `;
                    draftStatus.style.display = 'block';
                }
                currentRoutingSessionToken = 'idle';
                return;
            }
            try {
                const session = await window.NexusAuth.getSession();
                cacheSaved = await cacheGeneratedReport(
                    reportBlob,
                    docName,
                    activeReportType,
                    lastRequestContext?.topic || '',
                    session?.user?.id
                );
                await loadCachedReportForUser(session?.user?.id);
            } catch (error) {
                console.warn('[Nexus Report Cache] report downloaded but could not be cached:', error.message);
            }
            if (sProgressBar) sProgressBar.style.width = '100%';
            [sStep1, sStep2, sStep3, sStep4].forEach(s => markStep(s, 'success'));

            setTimeout(() => {
                resetScribeButtonState();
                if (activeReportButton) activeReportButton.disabled = false;
                currentRoutingSessionToken = "idle"; // Clear active session state
                if (sProgContainer) sProgContainer.style.display = 'none';
                if (draftStatus) {
                    // CRITICAL FIX: Extract the dynamic filename returned directly from your Python script execution run
                    const savedFile = docName || data.document_saved_at ||
                        "comprehensive_pre_research_proposal_report.docx";

                    draftStatus.className = 'success';
                    draftStatus.textContent = `Project writeup compiled successfully. Downloaded: ${savedFile}${cacheSaved ? ' A copy is cached on this device for 30 days.' : ' This report was not cached on this device.'}`;
                    draftStatus.style.display = 'block';
                }
                if (upgradeFromReportBtn) upgradeFromReportBtn.style.display = 'none';
                if (retryReportBtn) retryReportBtn.style.display = 'none';
                offerFeedback(data.reference, activeReportType);
            }, 600);
            return;
        }


        // --- PRODUCTION LOGIC VECTOR B: INTERCEPT PRIMARY LITERATURE SWEEPS ---
        if (currentRoutingSessionToken === "research_scan_active" && data.status === "success") {
            setTimeout(() => {
                handleResearchSuccess(data);
            }, 600);
        }
    }
    async function handleResearchSuccess(data, fromCache = false) {
        sendAnalytics('results_viewed', {
            ...(data.research_run_id ? {run_id: data.research_run_id} : {}),
            included_count: Number(data.counts?.included ?? (data.included || []).length),
            excluded_count: Number(data.counts?.excluded ?? (data.excluded || []).length),
            from_cache: fromCache
        });
        if (progressBar) progressBar.style.width = '100%';
        [step1, step2, step3, step4].forEach(s => markStep(s, 'success'));
        if (!fromCache) {
            const curr = await chrome.storage.local.get(["usage_count"]);
            await chrome.storage.local.set({
                usage_count: (curr.usage_count || 0) + 1,
                research_cache_key: lastRequestContext ? JSON.stringify({
                    topic: lastRequestContext.topic,
                    max_sources: lastRequestContext.max_sources,
                    domain: lastRequestContext.domain,
                    selected_inclusion_reasons: lastRequestContext.selected_inclusion_reasons
                }) : "",
                research_cache_result: data
            });
        }
        updateTierUI();
        runButton.disabled = false;
        if (btnSpinner) btnSpinner.style.display = 'none';
        if (btnText) btnText.innerText = 'Launch Research Agents';
        if (progressContainer) progressContainer.style.display = 'none';
        if (cancelScanBtn) cancelScanBtn.style.display = 'none';
        statusDiv.className = 'success';
        const lockedSources = Number(data.locked?.included_hidden || 0) + Number(data.locked?.excluded_hidden || 0);
        statusDiv.innerText = data.preview
            ? `${fromCache ? '♻️ Cached result loaded.' : '🎉 Scan complete.'} You are viewing a preview${lockedSources ? `: ${lockedSources} more sources are locked` : ''}. A Research Pack unlocks every source, the Excel dossier and the Word proposal.`
            : `${fromCache ? '♻️ Cached result loaded.' : '🎉 Scan complete.'} Your Excel research dossier is ready to download.`;
        statusDiv.style.display = 'block';
        if (reportMetadata) {
            const download = data.dossier_download || {};
            const remaining = download.unlimited ? null : Number(download.remaining);
            const dossierLocked = !download.unlimited && Number(download.limit) === 0;
            const quotaKnown = download.unlimited || Number.isFinite(remaining);
            reportMetadata.innerHTML = `
                <strong>Research reports</strong><br>
                Excel dossier: <span class="report-path" id="dossierFilename"></span><br>
                <button class="btn" id="downloadDossierBtn" type="button" style="width:auto; margin-top:8px; padding:8px 12px; font-size:0.78rem;">
                    Download Excel dossier
                </button>
                <span id="dossierDownloadStatus" role="status" style="display:block; margin-top:6px; color:var(--text-muted);"></span>
                <button class="btn" id="upgradeDossierBtn" type="button" style="display:none; width:auto; margin-top:8px; padding:8px 12px; font-size:0.78rem;">
                    View plans
                </button>
            `;
            const filenameElement = document.getElementById('dossierFilename');
            const downloadButton = document.getElementById('downloadDossierBtn');
            const downloadStatus = document.getElementById('dossierDownloadStatus');
            const upgradeButton = document.getElementById('upgradeDossierBtn');
            if (filenameElement) filenameElement.textContent = data.discovery_report_name || 'Unavailable';
            if (downloadStatus) {
                downloadStatus.textContent = download.unlimited
                    ? 'Unlimited dossier downloads available.'
                    : dossierLocked
                        ? 'The full Excel dossier is included with a Research Pack.'
                    : quotaKnown
                        ? `${remaining} of 3 free downloads remaining.`
                        : 'Your free download allowance will be checked before downloading.';
            }
            if (downloadButton) downloadButton.hidden = !data.research_run_id;
            if (Number.isFinite(remaining) && remaining <= 0) {
                if (downloadButton) downloadButton.disabled = true;
                if (downloadStatus && !dossierLocked) downloadStatus.textContent = 'You have used all 3 free dossier downloads.';
                if (upgradeButton) upgradeButton.style.display = 'inline-flex';
            }
            downloadButton?.addEventListener('click', async () => {
                downloadButton.disabled = true;
                let exhausted = false;
                if (downloadStatus) downloadStatus.textContent = 'Preparing your Excel dossier…';
                try {
                    const response = await fetch(
                        `${await getApiBaseUrl()}/v1/research/${encodeURIComponent(data.research_run_id)}/dossier`,
                        {headers: await getApiHeaders()}
                    );
                    if (!response.ok) {
                        let message = `Download failed (${response.status}).`;
                        const responseText = await response.text();
                        try {
                            const error = JSON.parse(responseText);
                            message = typeof error.detail === 'string' ? error.detail : (error.detail?.message || message);
                        } catch (parseError) {
                            if (responseText) message = responseText;
                        }
                        if (downloadStatus) downloadStatus.textContent = message;
                        if (response.status === 403) {
                            exhausted = true;
                            if (upgradeButton) upgradeButton.style.display = 'inline-flex';
                        }
                        return;
                    }
                    const blob = await response.blob();
                    const objectUrl = URL.createObjectURL(blob);
                    const link = document.createElement('a');
                    link.href = objectUrl;
                    link.download = data.discovery_report_name || 'research-dossier.xlsx';
                    document.body.appendChild(link);
                    link.click();
                    link.remove();
                    setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
                    const remainingHeader = response.headers.get('X-Dossier-Downloads-Remaining');
                    if (downloadStatus) {
                        downloadStatus.textContent = remainingHeader === 'unlimited'
                            ? 'Dossier downloaded. Unlimited downloads available.'
                            : `Dossier downloaded. ${remainingHeader} of 3 free downloads remaining.`;
                    }
                    if (remainingHeader !== 'unlimited' && Number(remainingHeader) <= 0) {
                        exhausted = true;
                        downloadButton.disabled = true;
                        if (upgradeButton) upgradeButton.style.display = 'inline-flex';
                    }
                } catch (error) {
                    if (downloadStatus) downloadStatus.textContent = `Download failed: ${error.message}`;
                } finally {
                    if (downloadButton.isConnected && !exhausted) downloadButton.disabled = false;
                }
            });
            upgradeButton?.addEventListener('click', () => openUpgradeFlow('extension_dossier'));
            reportMetadata.style.display = 'block';
        }

                activeSessionIncludedPapers = data.included || [];
                activeSessionExcludedPapers = data.excluded || [];
                activeResearchRunId = data.research_run_id || null;

                if (countInc) countInc.innerText = data.counts?.included ?? activeSessionIncludedPapers.length;
                if (countExc) countExc.innerText = data.counts?.excluded ?? activeSessionExcludedPapers.length;

                if (postMvpReviewSection) postMvpReviewSection.style.display = "block";
                if (synthesisFallbackCard) synthesisFallbackCard.style.display = "none";
                if (linkToSynthesisBtn) linkToSynthesisBtn.disabled = false;

                if (auditFilters) auditFilters.style.display = 'block';
                renderAuditRows();
                if (retryBtn) retryBtn.style.display = 'none';

                switchTab('dashboard');
        currentRoutingSessionToken = "idle";
    }

    runButton.onclick = async function(e) {
        e.preventDefault(); const topic = document.getElementById('topic').value.trim();
        if (!topic) return;
        const usage = await chrome.storage.local.get(["usage_count"]);
        if (!isLocalTestingInstall && (usage.usage_count || 0) >= FREE_LIMIT) {
            statusDiv.className = 'error';
            statusDiv.innerText = 'Freemium limit reached. Upgrade to continue scanning.';
            statusDiv.style.display = 'block';
            return;
        }

        const requestedSources = Number(maxSourcesSelect?.value || 5);
        const requestContext = {
            action: "trigger_nexus_scan",
            topic,
            max_sources: String(Math.min(requestedSources, isPaidUser ? 100 : 20)),
            domain: domainSelect?.value || "scholarly",
            uploaded_sources: await readUploads(),
            selected_inclusion_reasons: readInclusionReasons()
        };
        lastRequestContext = requestContext;
        if (upgradeFromScanBtn) upgradeFromScanBtn.style.display = 'none';
        const cacheKey = JSON.stringify({
            topic: requestContext.topic,
            max_sources: requestContext.max_sources,
            domain: requestContext.domain,
            selected_inclusion_reasons: requestContext.selected_inclusion_reasons,
            uploads: requestContext.uploaded_sources.map(upload => `${upload.name}:${upload.data.length}`)
        });
        const cached = await chrome.storage.local.get(["research_cache_key", "research_cache_result"]);
        // A cached preview is never replayed: after buying a pack the same query must fetch the full result.
        if (cached.research_cache_key === cacheKey && cached.research_cache_result && !cached.research_cache_result.preview) {
            currentRoutingSessionToken = "research_scan_active";
            await handleResearchSuccess(cached.research_cache_result, true);
            return;
        }

        currentRoutingSessionToken = "research_scan_active"; // Lock search session
        runButton.disabled = true; if (btnSpinner) btnSpinner.style.display = 'block';
        if (cancelScanBtn) cancelScanBtn.style.display = 'block';
        if (btnText) btnText.innerText = 'Searching...';
        if (statusDiv) statusDiv.style.display = 'none';
        if (progressContainer) progressContainer.style.display = 'block';
        if (progressBar) progressBar.style.width = '10%';

        markStep(step1, 'active');
        [step2, step3, step4].forEach(s => { if(s){ s.className = 'step-item'; s.querySelector('.step-icon').innerText = '⚫'; } });

        setTimeout(() => { if (runButton.disabled) { if (progressBar) progressBar.style.width = '35%'; markStep(step1, 'success'); markStep(step2, 'active'); } }, 1500);
        setTimeout(() => { if (runButton.disabled) { if (progressBar) progressBar.style.width = '65%'; markStep(step2, 'success'); markStep(step3, 'active'); } }, 3500);
        setTimeout(() => { if (runButton.disabled) { if (progressBar) progressBar.style.width = '85%'; markStep(step3, 'success'); markStep(step4, 'active'); } }, 6000);

        try {
            await sendBackgroundRequest(requestContext);
        } catch (error) {
            runButton.disabled = false;
            if (cancelScanBtn) cancelScanBtn.style.display = 'none';
            if (statusDiv) {
                statusDiv.className = 'error';
                statusDiv.innerText = `Upload failed: ${error.message}`;
                statusDiv.style.display = 'block';
            }
            sendAnalytics('error_displayed', {surface: 'scan', error_code: 'client_error'});
        }
    };

    retryBtn?.addEventListener('click', () => {
        if (!lastRequestContext) return;
        retryBtn.style.display = 'none';
        currentRoutingSessionToken = lastRequestContext.action === 'trigger_nexus_scan'
            ? 'research_scan_active'
            : 'docx_generation_active';
        if (lastRequestContext.action === 'trigger_nexus_scan') {
            runButton.disabled = true;
            if (progressContainer) progressContainer.style.display = 'block';
            if (btnSpinner) btnSpinner.style.display = 'block';
            if (btnText) btnText.innerText = 'Retrying...';
            if (cancelScanBtn) cancelScanBtn.style.display = 'block';
        } else if (activeReportButton) {
            activeReportButton.disabled = true;
            if (sProgContainer) sProgContainer.style.display = 'block';
            if (activeReportType === 'full_starter') {
                if (fullPaperSpinner) fullPaperSpinner.style.display = 'block';
                if (fullDraftBtnText) fullDraftBtnText.innerText = 'Retrying complete literature review...';
            } else {
                if (proposalSpinner) proposalSpinner.style.display = 'block';
                if (draftBtnText) draftBtnText.innerText = 'Retrying proposal...';
            }
            if (cancelReportBtn) cancelReportBtn.style.display = 'block';
        }
        sendBackgroundRequest(lastRequestContext).catch(error => {
            reportProcessingActive = false;
            resetScribeButtonState();
            if (retryReportBtn) retryReportBtn.style.display = 'block';
            if (draftStatus) {
                draftStatus.className = 'error';
                draftStatus.innerText = `Processing could not start: ${error.message}`;
                draftStatus.style.display = 'block';
            }
        });
    });

    cancelScanBtn?.addEventListener('click', () => {
        currentRoutingSessionToken = 'idle';
        runButton.disabled = false;
        if (btnSpinner) btnSpinner.style.display = 'none';
        if (btnText) btnText.innerText = 'Launch Research Agents';
        if (progressContainer) progressContainer.style.display = 'none';
        cancelScanBtn.style.display = 'none';
        if (retryBtn && lastRequestContext?.action === 'trigger_nexus_scan') retryBtn.style.display = 'block';
        if (statusDiv) {
            statusDiv.className = 'error';
            statusDiv.innerText = 'Research scan stopped. You can retry with the same context.';
            statusDiv.style.display = 'block';
        }
    });

    if (draftDocBtn) {
        draftDocBtn.onclick = async function(e) {
            generateDocument(e, "proposal", draftDocBtn, "draftBtnText");
        };
    }

    if (fullDraftDocBtn) {
        fullDraftDocBtn.onclick = async function(e) {
            await refreshEntitlements();
            if (!isPaidUser && !isLocalTestingInstall) {
                if (draftStatus) {
                    draftStatus.className = 'error';
                    draftStatus.innerText = "The Complete Literature Review is available to paid users. Get a Research Pack, then try again.";
                    draftStatus.style.display = 'block';
                }
                if (upgradeFromReportBtn) upgradeFromReportBtn.style.display = 'block';
                return;
            }
            generateDocument(e, "full_starter", fullDraftDocBtn, null);
        };
    }

    async function generateDocument(event, reportType, button, buttonTextId) {
        event.preventDefault();

            // PROBLEM 2 RESOLVED: Guaranteed persistent reference dataset bounds.
            // This ensures clicking synthesis a second or third time will never stall the pipeline.
            currentRoutingSessionToken = "docx_generation_active";
            activeReportButton = button;
            activeReportType = reportType;
            reportGenerationCancelled = false;
            reportProcessingActive = true;
            lastRequestContext = {
                action: "trigger_docx_generation",
                topic: document.getElementById('topic').value.trim() || "ai token optimization techniques",
                included_sources: activeSessionIncludedPapers,
                research_run_id: activeResearchRunId,
                preview: !isPaidUser && !isLocalTestingInstall && reportType === 'proposal',
                uploaded_sources: await readUploads(),
                report_type: reportType,
                domain: domainSelect?.value || "scholarly",
                max_sources: Number(maxSourcesSelect?.value || 5)
            };
            hideFeedback();
            button.disabled = true;
            if (reportType === 'full_starter') {
                if (fullPaperSpinner) fullPaperSpinner.style.display = 'block';
            } else if (proposalSpinner) {
                proposalSpinner.style.display = 'block';
            }
            if (buttonTextId && document.getElementById(buttonTextId)) document.getElementById(buttonTextId).innerText = 'Compiling...';
            if (reportType === 'full_starter' && fullDraftBtnText) fullDraftBtnText.innerText = 'Generating complete literature review...';
            if (cancelReportBtn) cancelReportBtn.style.display = 'block';
            if (retryReportBtn) retryReportBtn.style.display = 'none';
            if (draftStatus) draftStatus.style.display = 'none';
            if (sProgContainer) sProgContainer.style.display = 'block';
            if (sProgressBar) sProgressBar.style.width = '10%';

            markStep(sStep1, 'active');
            [sStep2, sStep3, sStep4].forEach(s => { if(s){ s.className = 'step-item'; s.querySelector('.step-icon').innerText = '⚫'; } });

            setTimeout(() => { if (button.disabled) { if (sProgressBar) sProgressBar.style.width = '30%'; markStep(sStep1, 'success'); markStep(sStep2, 'active'); } }, 1200);
            setTimeout(() => { if (button.disabled) { if (sProgressBar) sProgressBar.style.width = '60%'; markStep(sStep2, 'success'); markStep(sStep3, 'active'); } }, 2800);
            setTimeout(() => { if (button.disabled) { if (sProgressBar) sProgressBar.style.width = '85%'; markStep(sStep3, 'success'); markStep(sStep4, 'active'); } }, 5000);

            sendBackgroundRequest(lastRequestContext).catch(error => {
                reportProcessingActive = false;
                resetScribeButtonState();
                if (retryReportBtn) retryReportBtn.style.display = 'block';
                if (draftStatus) {
                    draftStatus.className = 'error';
                    draftStatus.innerText = `Processing could not start: ${error.message}`;
                    draftStatus.style.display = 'block';
                }
            });
    }

    cancelReportBtn?.addEventListener('click', () => {
        reportGenerationCancelled = true;
        reportProcessingActive = false;
        currentRoutingSessionToken = 'idle';
        resetScribeButtonState();
        if (sProgContainer) sProgContainer.style.display = 'none';
        if (cancelReportBtn) cancelReportBtn.style.display = 'none';
        if (retryReportBtn) retryReportBtn.style.display = lastRequestContext?.action === 'trigger_docx_generation' ? 'block' : 'none';
        if (draftStatus) {
            draftStatus.className = 'error';
            draftStatus.innerText = 'Report generation stopped. You can retry with the same research context.';
            draftStatus.style.display = 'block';
        }
    });

    retryReportBtn?.addEventListener('click', () => {
        if (!lastRequestContext || lastRequestContext.action !== 'trigger_docx_generation') return;
        retryReportBtn.style.display = 'none';
        reportGenerationCancelled = false;
        reportProcessingActive = true;
        currentRoutingSessionToken = 'docx_generation_active';
        activeReportType = lastRequestContext.report_type;
        activeReportButton = activeReportType === 'full_starter' ? fullDraftDocBtn : draftDocBtn;
        generateDocument({ preventDefault() {} }, activeReportType, activeReportButton, activeReportType === 'full_starter' ? 'fullDraftBtnText' : 'draftBtnText');
    });

    function resetScribeButtonState() {
        if (draftDocBtn) {
            draftDocBtn.disabled = false;
            if (proposalSpinner) proposalSpinner.style.display = 'none';
            if (draftBtnText) draftBtnText.innerText = 'Generate Pre-Research Proposal';
        }
        if (fullDraftDocBtn) {
            fullDraftDocBtn.disabled = false;
            if (fullPaperSpinner) fullPaperSpinner.style.display = 'none';
            if (fullDraftBtnText) fullDraftBtnText.innerText = 'Generate Complete Literature Review';
        }
        if (cancelReportBtn) cancelReportBtn.style.display = 'none';
    }
});
