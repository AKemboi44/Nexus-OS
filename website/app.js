(() => {
    'use strict';

    const SUPABASE_URL = 'https://mdjgrtkjjcwmhuhpsjsk.supabase.co';
    const SUPABASE_PUBLISHABLE_KEY = 'sb_publishable_xp5XQM7DThmmgsVpG4wZog_QVVnOOmw';
    const API_URL = 'https://nexus-os-production-2e14.up.railway.app';
    const SUPPORT_WHATSAPP = '254743852707';
    const SUPPORT_EMAIL = 'brisklightke@gmail.com';
    const SESSION_KEY = 'nexus_web_supabase_session';
    const FREE_MAX_SOURCES = 20;
    const FREE_MAX_CRITERIA = 3;
    const PAID_MAX_CRITERIA = 8;
    const LIBRARY_PAGE_SIZE = 5;
    const HISTORY_PAGE_SIZE = 3;
    const RESULT_PAGE_SIZE = 3;
    const SESSION_TICK_MARGIN_SECONDS = 60;

    const byId = id => document.getElementById(id);
    const dialog = byId('authDialog');
    const authStatus = byId('authStatus');
    const scanStatus = byId('scanStatus');
    const reportStatus = byId('reportStatus');
    let session = null;
    let paid = false;
    let scansRemaining = null;
    let plan = null;
    let planEndsAt = null;
    let packInfo = null;
    let packs = [];
    let authMode = 'signin';
    let activeResult = null;
    let researchRuns = [];
    let savedDossiers = [];
    let savedSources = [];
    let historyPage = 0;
    let sourcesPage = 0;
    let resultIncludedSources = [];
    let resultExcludedSources = [];
    let resultTotals = {included: 0, excluded: 0};
    let resultLocked = {included: 0, excluded: 0};
    let includedSourcesPage = 0;
    let excludedSourcesPage = 0;

    function setMessage(element, message, type = '') {
        if (!element) return;
        const keepCallout = element.classList.contains('status-callout');
        element.textContent = message;
        element.className = `form-message${type ? ` ${type}` : ''}${keepCallout ? ' status-callout' : ''}`;
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
        sessionStorage.removeItem('nexus_web_supabase_pkce');
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
        const hash = new URLSearchParams(url.hash.slice(1));
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
        byId('accountEmail').textContent = displayName(session?.user?.email);
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

    function displayName(email) {
        const localPart = String(email || '').split('@')[0] || 'Researcher';
        const name = localPart.replace(/[._+-].*$/, '').replace(/\d+/g, '');
        return name ? `${name.charAt(0).toUpperCase()}${name.slice(1)}` : 'Researcher';
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

    function extractErrorMessage(payload, status) {
        if (!payload) return `Request failed (${status}).`;
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
            return `Request failed (${status}).`;
        }
    }

    async function apiJson(path, options = {}) {
        const response = await apiFetch(path, options);
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) {
            const message = extractErrorMessage(payload, response.status);
            const error = new Error(message);
            error.status = response.status;
            error.payload = payload;
            throw error;
        }
        return payload;
    }

    const analyticsSessionId = (window.crypto && crypto.randomUUID)
        ? crypto.randomUUID()
        : `${Date.now().toString(36)}${Math.random().toString(36).slice(2)}`;

    // Fire-and-forget product telemetry. Numbers, ids and enums only: never topics or text.
    function track(event, context = {}) {
        if (!session) return;
        apiFetch('/v1/analytics', {
            method: 'POST',
            body: JSON.stringify({session_id: analyticsSessionId, source: 'web', event, context})
        }).catch(() => {});
    }

    // --- upgrade prompts: one reusable component, every click tracked by placement -------------------

    function formatPrice(price) {
        const amount = Number(price);
        return Number.isInteger(amount) ? `$${amount}` : `$${amount.toFixed(2)}`;
    }

    function startingPrice() {
        return packs.length ? formatPrice(Math.min(...packs.map(pack => Number(pack.price)))) : null;
    }

    function packButtonLabel() {
        const from = startingPrice();
        return from ? `Unlock from ${from}` : 'Get a Research Pack';
    }

    function pricingFeature(text) {
        return Object.assign(document.createElement('li'), {textContent: text});
    }

    function pricingCard(pack, featured) {
        const card = document.createElement('article');
        card.className = `pricing-card${featured ? ' featured' : ''}`;
        const parts = [];
        if (pack.badge) parts.push(Object.assign(document.createElement('span'), {className: 'pricing-badge', textContent: pack.badge}));
        parts.push(Object.assign(document.createElement('h4'), {textContent: pack.name}));
        const price = document.createElement('div');
        price.className = 'pricing-price';
        price.append(
            Object.assign(document.createElement('span'), {className: 'amount', textContent: formatPrice(pack.price)}),
            Object.assign(document.createElement('span'), {className: 'unit', textContent: 'one-time'}),
        );
        parts.push(price);
        parts.push(Object.assign(document.createElement('p'), {className: 'pricing-per-scan', textContent: `Just $${pack.per_scan} per scan`}));
        const features = document.createElement('ul');
        features.className = 'pricing-features';
        features.append(
            pricingFeature(`${pack.scans} scans`),
            pricingFeature('Full Excel audit dossier'),
            pricingFeature('Full Word proposal reports'),
            pricingFeature(`Valid for ${pack.validity_days} days`),
        );
        parts.push(features);
        const buy = Object.assign(document.createElement('button'), {
            type: 'button', className: 'button button-cta', textContent: `Get ${pack.name} · ${formatPrice(pack.price)}`,
        });
        buy.dataset.pack = pack.id;
        parts.push(buy);
        card.append(...parts);
        return card;
    }

    function teamCard() {
        const card = document.createElement('article');
        card.className = 'pricing-card team';
        const contact = Object.assign(document.createElement('button'), {
            type: 'button', className: 'button button-outline pricing-contact', textContent: 'Contact us',
        });
        contact.dataset.contact = 'true';
        card.append(
            Object.assign(document.createElement('span'), {className: 'pricing-badge', textContent: 'For labs and teams'}),
            Object.assign(document.createElement('h4'), {textContent: 'Lab / Team'}),
            Object.assign(document.createElement('div'), {className: 'pricing-price'}),
            Object.assign(document.createElement('p'), {
                className: 'pricing-per-scan', textContent: 'Shared scans for research groups',
            }),
            Object.assign(document.createElement('p'), {
                className: 'pricing-note',
                textContent: 'We are shaping team plans with early labs. Tell us your group size and what you need.',
            }),
            contact,
        );
        card.querySelector('.pricing-price').append(
            Object.assign(document.createElement('span'), {className: 'amount', textContent: 'Custom'}),
        );
        return card;
    }

    function renderPricing() {
        const grid = byId('pricingGrid');
        if (!packs.length) {
            const retry = Object.assign(document.createElement('button'), {
                type: 'button', className: 'button button-primary', textContent: 'Try again',
            });
            retry.addEventListener('click', () => {
                grid.replaceChildren(Object.assign(document.createElement('p'), {
                    className: 'pricing-loading', textContent: 'Loading prices…',
                }));
                loadPackInfo();
            });
            grid.replaceChildren(Object.assign(document.createElement('p'), {
                className: 'pricing-loading', textContent: 'Prices could not be loaded.',
            }), retry);
            return;
        }
        grid.replaceChildren(...packs.map((pack, index) => pricingCard(pack, index === 0)), teamCard());
    }

    function updateStickyUpgrade() {
        const bar = byId('stickyUpgrade');
        bar.hidden = paid || !session || !activeResult;
        if (bar.hidden) return;
        const from = startingPrice();
        byId('stickyUpgradeText').textContent = from ? `Full downloads from ${from}` : 'Unlock full downloads';
    }

    function openUpgrade(placement) {
        track('upgrade_cta_clicked', {placement});
        byId('plansCard').hidden = false;
        byId('plansCard').scrollIntoView({behavior: 'smooth', block: 'center'});
        if (!packs.length) loadPackInfo();
    }

    function showUpgradePrompt(container, {headline, description, placement}) {
        if (!container) return;
        const title = document.createElement('strong');
        title.textContent = headline;
        const text = document.createElement('p');
        text.textContent = description;
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'button button-cta';
        button.textContent = packButtonLabel();
        button.addEventListener('click', () => openUpgrade(placement));
        container.replaceChildren(title, text, button);
        container.hidden = false;
    }

    function hideUpgradePrompts() {
        ['scanUpgrade', 'reportUpgrade'].forEach(id => {
            const node = byId(id);
            if (node) { node.hidden = true; node.replaceChildren(); }
        });
    }

    // The header button is visible to anyone who cannot already do everything: free users, and pack
    // buyers who have used all their scans. It is not tied to `paid`, which stays true for the latter.
    function updateUpgradeButton() {
        const button = byId('upgradePlan');
        const exhausted = paid && scansRemaining === 0;
        button.hidden = !session;
        button.textContent = exhausted ? 'Buy more scans' : paid ? 'Add scans' : 'Upgrade';
    }

    const LOW_SCANS = 3;
    const DAY_MS = 24 * 60 * 60 * 1000;

    function formatDate(value) {
        const date = new Date(value);
        return Number.isNaN(date.getTime())
            ? '' : date.toLocaleDateString(undefined, {year: 'numeric', month: 'short', day: 'numeric'});
    }

    function setPlanNotice(message, type = '') {
        const notice = byId('planNotice');
        setMessage(notice, message, type);
        notice.hidden = !message;
        renderPlan();
    }

    // "Your plan": what the user bought, how many scans are left and when the pack expires. It stays
    // on screen for pack buyers, and turns into a nudge to buy more as the balance runs down.
    function renderPlan() {
        const card = byId('planCard');
        const notice = byId('planNotice');
        const hasPlan = Boolean(plan) && scansRemaining !== null;
        card.hidden = !hasPlan && notice.hidden;
        byId('planMain').hidden = byId('planActions').hidden = !hasPlan;
        byId('pricingTitle').textContent = hasPlan ? 'Add more scans' : 'Unlock your full dossier and report';
        byId('pricingLead').textContent = hasPlan
            ? 'New scans are added to your balance. Pick the pack that fits your next project.'
            : 'Download the complete Excel audit and Word proposal for every scan you run. Pick the pack that fits your project.';
        card.classList.remove('is-low', 'is-empty', 'is-expired');
        if (!hasPlan) return;

        const left = scansRemaining;
        const total = Math.max(Number(plan.scans_purchased) || 0, left, 1);
        const percent = Math.round((left / total) * 100);
        const endsAt = planEndsAt ? new Date(planEndsAt) : null;
        const msLeft = endsAt && !Number.isNaN(endsAt.getTime()) ? endsAt.getTime() - Date.now() : null;
        const expired = msLeft !== null && msLeft <= 0;
        const state = expired ? 'is-expired' : left === 0 ? 'is-empty' : left <= LOW_SCANS || percent <= 20 ? 'is-low' : '';
        if (state) card.classList.add(state);

        byId('planRing').style.setProperty('--plan-progress', `${expired ? 0 : percent}%`);
        byId('planRing').setAttribute('aria-valuenow', String(expired ? 0 : percent));
        byId('planRingValue').textContent = String(expired ? 0 : left);
        byId('planName').textContent = plan.pack_name;
        byId('planBalance').textContent = expired
            ? `${left} unused ${left === 1 ? 'scan' : 'scans'} expired`
            : `${left} of ${total} scans left`;
        const packs = Array.isArray(plan.packs) ? plan.packs : [];
        byId('planExpiry').textContent = [
            msLeft === null ? '' : expired
                ? `Expired ${formatDate(planEndsAt)}`
                : `Valid until ${formatDate(planEndsAt)} · ${Math.max(1, Math.ceil(msLeft / DAY_MS))} days left`,
            packs.length > 1 ? `Combined from ${packs.map(pack => pack.scans).join(' + ')} scans` : '',
        ].filter(Boolean).join(' · ');

        const nudge = byId('planNudge');
        nudge.hidden = !state;
        nudge.textContent = expired ? 'Your pack has expired. Add a new pack to keep scanning.'
            : left === 0 ? 'You have used all your scans. Add more to keep going.'
            : state ? `Running low: only ${left} ${left === 1 ? 'scan' : 'scans'} left. Add more so your work is not interrupted.` : '';
        byId('planAddScans').className = state ? 'button button-cta' : 'button button-outline';
    }

    // --- free-tier preview cards: what the files contain, with the rest locked --------------------
    // The sheets the workbook really has (kept in step with research_pipeline.py by a test).
    const EXCEL_SHEETS = [
        'Core Themes', 'Executive Summary', 'Included Evidence', 'Excluded Candidates',
        'Research Areas', 'Research Opportunities', 'Run Audit Configuration',
    ];
    let wordPreview = {runId: null, status: 'idle', snapshot: null, message: ''};

    function isPreviewMode(data) {
        return !paid && Boolean(data && data.preview);
    }

    // Locked content is drawn as empty placeholder bars: nothing hidden is ever in the page.
    function ghostLines(count) {
        const wrap = document.createElement('div');
        wrap.className = 'ghost-lines';
        wrap.setAttribute('aria-hidden', 'true');
        for (let i = 0; i < count; i++) {
            const bar = document.createElement('span');
            bar.className = `ghost ghost-${['l', 'm', 'l', 's'][i % 4]}`;
            wrap.append(bar);
        }
        return wrap;
    }

    function unlockButton(label, placement) {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'button button-cta snapshot-unlock';
        button.textContent = label;
        button.addEventListener('click', () => openUpgrade(placement));
        return button;
    }

    function authorsText(source) {
        const authors = Array.isArray(source.authors) ? source.authors.slice(0, 2).join(', ') : String(source.authors || '');
        return authors.slice(0, 60);
    }

    function excelCard(data) {
        const card = document.createElement('article');
        card.className = 'snapshot-card snapshot-excel';
        appendText(card, 'h4', 'Excel audit dossier');
        const counts = data.counts || {};
        appendText(card, 'p', `${counts.reviewed ?? 0} sources reviewed · ${counts.included ?? 0} included · ${counts.excluded ?? 0} filtered`, 'snapshot-totals');

        const sheet = document.createElement('div');
        sheet.className = 'snapshot-sheet';
        sheet.setAttribute('role', 'table');
        sheet.setAttribute('aria-label', 'Preview of the Excel dossier');
        const addRow = (cells, className) => {
            const row = document.createElement('div');
            row.className = `sheet-row ${className}`;
            row.setAttribute('role', 'row');
            cells.forEach(text => appendText(row, 'span', text, 'sheet-cell'));
            sheet.append(row);
            return row;
        };
        addRow(['Title', 'Authors', 'Year', 'Reason'], 'sheet-head');
        (data.included || []).slice(0, 3).forEach(source => addRow(
            [source.title || 'Untitled source', authorsText(source), String(source.year || ''), source.inclusion_reason || 'Included'],
            'sheet-real'
        ));
        const hidden = Number(data.locked?.included_hidden || 0);
        for (let i = 0; i < Math.min(4, hidden); i++) {
            const row = document.createElement('div');
            row.className = 'sheet-row sheet-ghost';
            row.setAttribute('aria-hidden', 'true');
            ['l', 'm', 's', 'm'].forEach(size => {
                const cell = document.createElement('span');
                cell.className = `sheet-cell ghost ghost-${size}`;
                row.append(cell);
            });
            sheet.append(row);
        }
        card.append(sheet);
        appendText(card, 'p', hidden > 0 ? `🔒 +${hidden} more included sources, plus all filtered candidates and their reasons, are in the full file.` : '🔒 The full file adds the filtered candidates and the reason for each decision.', 'snapshot-lock');
        appendText(card, 'p', `Full workbook, ${EXCEL_SHEETS.length} sheets: ${EXCEL_SHEETS.join(', ')}.`, 'snapshot-sheets');
        card.append(unlockButton(`Unlock the full dossier${startingPrice() ? ` from ${startingPrice()}` : ''}`, 'snapshot_excel'));
        return card;
    }

    function wordCard(data) {
        const card = document.createElement('article');
        card.className = 'snapshot-card snapshot-word';
        appendText(card, 'h4', 'Word proposal');
        appendText(card, 'p', 'A structured proposal written from your included sources, with citations and references.', 'snapshot-totals');
        const body = document.createElement('div');
        body.id = 'snapshotWordBody';
        body.className = 'snapshot-word-body';
        card.append(body);
        renderWordBody(body, data);
        return card;
    }

    function renderWordBody(body, data) {
        const state = wordPreview;
        const parts = [];
        if (state.status === 'ready' && state.snapshot) {
            const snap = state.snapshot;
            const page = document.createElement('div');
            page.className = 'snapshot-page';
            appendText(page, 'strong', snap.title || data.query || 'Research proposal', 'snapshot-page-title');
            if (snap.opening_paragraph) appendText(page, 'p', snap.opening_paragraph, 'snapshot-opening');
            parts.push(page);
            const outline = document.createElement('ol');
            outline.className = 'snapshot-outline';
            (snap.sections || []).forEach((section, index) => {
                const item = document.createElement('li');
                item.className = index === 0 ? 'outline-open' : 'outline-locked';
                item.dataset.level = String(section.level || 1);
                appendText(item, 'span', `${index === 0 ? '' : '🔒 '}${section.title}`, 'outline-title');
                appendText(item, 'span', `${section.words} words`, 'outline-words');
                outline.append(item);
            });
            parts.push(outline);
            parts.push(Object.assign(document.createElement('p'), {
                className: 'snapshot-counts',
                textContent: `${snap.citation_count} in-text citations · ${snap.reference_count} references · ${snap.total_words} words`,
            }));
            parts.push(ghostLines(4));
            parts.push(Object.assign(document.createElement('p'), {
                className: 'snapshot-lock',
                textContent: `🔒 ${snap.locked_sections} sections are locked: they are included in a Research Pack.`,
            }));
            parts.push(unlockButton('Unlock the full proposal', 'snapshot_word'));
        } else if (state.status === 'used') {
            parts.push(ghostLines(5));
            parts.push(Object.assign(document.createElement('p'), {className: 'snapshot-lock', textContent: `🔒 ${state.message}`}));
            parts.push(unlockButton('Unlock the full proposal', 'snapshot_word'));
        } else {
            parts.push(ghostLines(5));
            if (state.status === 'error') {
                parts.push(Object.assign(document.createElement('p'), {className: 'snapshot-error', textContent: state.message}));
            }
            const button = document.createElement('button');
            button.type = 'button';
            button.className = 'button button-primary snapshot-preview';
            button.id = 'previewProposal';
            button.disabled = state.status === 'loading';
            button.textContent = state.status === 'loading' ? 'Writing your preview…'
                : state.status === 'error' ? 'Try again' : 'Preview my proposal (free)';
            button.addEventListener('click', previewProposal);
            parts.push(button);
            parts.push(Object.assign(document.createElement('p'), {
                className: 'snapshot-note',
                textContent: 'You get one free preview each month: the opening paragraph and the outline.',
            }));
        }
        body.replaceChildren(...parts);
    }

    async function previewProposal() {
        const runId = activeResult && activeResult.research_run_id;
        if (!runId || wordPreview.status === 'loading') return;
        track('deliverable_clicked', {kind: 'proposal_preview'});
        wordPreview = {runId, status: 'loading', snapshot: null, message: ''};
        refreshWordCard();
        try {
            const response = await apiJson('/v1/reports', {
                method: 'POST',
                body: JSON.stringify({
                    topic: activeResult.query || byId('topic').value.trim(),
                    research_run_id: runId,
                    preview: true,
                    report_type: 'proposal',
                    domain: byId('domain').value,
                    max_sources: Number(byId('maxSources').value),
                }),
            });
            if (response.status !== 'snapshot' || !response.snapshot) throw new Error('The preview could not be created.');
            wordPreview = {runId, status: 'ready', snapshot: response.snapshot, message: ''};
        } catch (error) {
            const detail = error.payload && error.payload.detail;
            wordPreview = detail && detail.error_code === 'upgrade_required'
                ? {runId, status: 'used', snapshot: null, message: detail.message || 'You have used your free preview this month.'}
                : {runId, status: 'error', snapshot: null, message: error.message || 'The preview could not be created. Please try again.'};
        }
        if (activeResult && activeResult.research_run_id === runId) refreshWordCard();
    }

    function refreshWordCard() {
        const body = byId('snapshotWordBody');
        if (body && activeResult) renderWordBody(body, activeResult);
    }

    // Free users see two preview cards instead of the download buttons; everyone with a pack keeps the buttons.
    function renderDeliverables(data) {
        const preview = isPreviewMode(data);
        byId('downloadExcel').hidden = preview;
        byId('proposalReport').hidden = preview;
        const container = byId('snapshotCards');
        container.hidden = !preview;
        if (!preview) {
            container.replaceChildren();
            return;
        }
        if (wordPreview.runId !== data.research_run_id) {
            wordPreview = {runId: data.research_run_id, status: 'idle', snapshot: null, message: ''};
        }
        container.replaceChildren(excelCard(data), wordCard(data));
    }

    function renderUpsells(data) {
        const banner = byId('upgradeBanner');
        const upsell = byId('deliverablesUpsell');
        banner.hidden = paid;
        upsell.hidden = paid || isPreviewMode(data);
        updateStickyUpgrade();
        if (paid) return;
        const remaining = data && data.queries_remaining !== null && data.queries_remaining !== undefined
            ? Number(data.queries_remaining) : null;
        const from = startingPrice();
        const priceText = from ? ` from ${from}` : '';
        byId('upgradeBannerText').textContent = remaining === 0
            ? `You have used your free scan. Unlock the full Excel dossier and Word report${priceText}. One payment, no subscription.`
            : `You are on the free plan. Unlock the full Excel dossier and Word report${priceText}. One payment, no subscription.`;
        byId('upgradeBannerButton').textContent = packButtonLabel();
        const starter = packs[0];
        byId('deliverablesUpsellText').textContent = starter
            ? `Packs start at ${formatPrice(starter.price)} for ${starter.scans} scans, with full Excel and Word downloads.`
            : 'Get a Research Pack for more scans and full downloads.';
        byId('deliverablesUpsellButton').textContent = packButtonLabel();
    }

    async function refreshEntitlement() {
        const response = await apiFetch(`/v1/entitlements/${encodeURIComponent(session.user.id)}`);
        const result = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(extractErrorMessage(result, response.status) || 'Could not refresh subscription status.');
        paid = response.ok && Boolean(result.active);
        scansRemaining = result.scans_remaining === null || result.scans_remaining === undefined
            ? null : Number(result.scans_remaining);
        plan = result.plan || null;
        planEndsAt = result.ends_at || null;
        renderPlan();
        document.querySelectorAll('[data-paid-only]').forEach(option => {
            option.disabled = !paid;
            if (!paid) option.textContent = option.textContent.replace(' · paid', ' · upgrade required');
            else option.textContent = option.textContent.replace(' · upgrade required', ' · paid');
        });
        if (!paid && Number(byId('maxSources').value) > FREE_MAX_SOURCES) byId('maxSources').value = '20';
        if (!paid && byId('domain').value === 'legal') byId('domain').value = 'scholarly';
        byId('fullReport').hidden = false;
        updateUpgradeButton();
        renderUpsells(activeResult);
        if (activeResult) renderDeliverables(activeResult);
        byId('criteriaLimit').textContent = `(up to ${paid ? PAID_MAX_CRITERIA : FREE_MAX_CRITERIA}, optional)`;
        byId('criteriaHint').textContent = (paid
            ? `Choose up to ${PAID_MAX_CRITERIA} criteria to focus your evidence review.`
            : `Free accounts can choose up to ${FREE_MAX_CRITERIA} criteria. Upgrade to choose up to ${PAID_MAX_CRITERIA}.`)
            + ' If you choose none, we apply: cited, recent, and unique and topic-relevant.';
    }

    function appendText(parent, tag, text, className = '') {
        const element = document.createElement(tag);
        if (className) element.className = className;
        element.textContent = text || '';
        parent.appendChild(element);
        return element;
    }

    function cleanDisplayedSourceText(text) {
        const value = String(text || '');
        const words = Array.from(value.matchAll(/[A-Za-z0-9][A-Za-z0-9'’-]*/g));
        if (words.length < 2) return value;

        const output = [];
        let cursor = 0;
        let index = 0;
        while (index < words.length) {
            const first = words[index];
            let lastIndex = index;
            while (lastIndex + 1 < words.length) {
                const following = words[lastIndex + 1];
                const separator = value.slice(
                    words[lastIndex].index + words[lastIndex][0].length,
                    following.index
                );
                if (
                    following[0].toLocaleLowerCase() !== first[0].toLocaleLowerCase()
                    || !/^\s+$/.test(separator)
                ) {
                    break;
                }
                lastIndex += 1;
            }

            output.push(value.slice(cursor, first.index), first[0]);
            cursor = words[lastIndex].index + words[lastIndex][0].length;
            index = lastIndex + 1;
        }
        output.push(value.slice(cursor));
        return output.join('');
    }

    function renderHistory() {
        const container = byId('historyList');
        container.replaceChildren();
        const query = byId('historySearch').value.trim().toLowerCase();
        const ageDays = byId('historyDateFilter').value;
        const cutoff = ageDays === 'all' ? 0 : Date.now() - Number(ageDays) * 24 * 60 * 60 * 1000;
        const filteredRuns = researchRuns.filter(run => {
            const matchesQuery = String(run.query || '').toLowerCase().includes(query);
            const createdAt = Date.parse(run.created_at || '');
            const matchesDate = !cutoff || !Number.isFinite(createdAt) || createdAt >= cutoff;
            return matchesQuery && matchesDate;
        });
        if (!filteredRuns.length) {
            appendText(container, 'p', researchRuns.length
                ? 'No research matches those filters.'
                : 'Your completed scans will appear here.', 'empty-state');
            byId('historyPagination').hidden = true;
            return;
        }
        const dossierByRun = new Map(savedDossiers.map(item => [item.payload?.research_run_id, item]));
        const totalPages = Math.ceil(filteredRuns.length / HISTORY_PAGE_SIZE);
        historyPage = Math.min(historyPage, totalPages - 1);
        const pageRuns = filteredRuns.slice(historyPage * HISTORY_PAGE_SIZE, (historyPage + 1) * HISTORY_PAGE_SIZE);
        pageRuns.forEach(run => {
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
        byId('historyPagination').hidden = filteredRuns.length <= HISTORY_PAGE_SIZE;
        byId('historyPageLabel').textContent = `${historyPage + 1} / ${totalPages} · ${filteredRuns.length} scans`;
        byId('historyPrev').disabled = historyPage === 0;
        byId('historyNext').disabled = historyPage >= totalPages - 1;
    }

    async function loadHistory() {
        const [runs, dossiers, sources] = await Promise.all([
            apiJson('/v1/research?limit=100'),
            apiJson('/v1/dossiers'),
            apiJson('/v1/sources')
        ]);
        researchRuns = runs;
        savedDossiers = dossiers;
        savedSources = sources;
        historyPage = 0;
        sourcesPage = 0;
        renderHistory();
        renderSavedSources();
    }

    function renderSavedSources() {
        const container = byId('savedSourcesList');
        container.replaceChildren();
        byId('sourceCount').textContent = String(savedSources.length);
        const query = byId('sourceSearch').value.trim().toLowerCase();
        const matches = savedSources.filter(record => {
            const source = record.source || {};
            return [source.title, source.abstract, source.year, source.venue, source.doi, source.url]
                .some(value => String(value || '').toLowerCase().includes(query));
        });
        if (!matches.length) {
            appendText(container, 'p', savedSources.length
                ? 'No saved sources match your search.'
                : 'Save a source from a scan to keep it here.', 'empty-state');
            byId('sourcePagination').hidden = true;
            return;
        }
        const totalPages = Math.ceil(matches.length / LIBRARY_PAGE_SIZE);
        sourcesPage = Math.min(sourcesPage, totalPages - 1);
        matches.slice(sourcesPage * LIBRARY_PAGE_SIZE, (sourcesPage + 1) * LIBRARY_PAGE_SIZE).forEach(record => {
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
            appendText(row, 'small', [source.authors?.slice?.(0, 2).join(', '), source.year, source.venue || source.journal]
                .filter(Boolean).join(' · '));
            if (source.abstract) {
                appendText(
                    row,
                    'p',
                    cleanDisplayedSourceText(source.abstract).slice(0, 240),
                    'saved-source-abstract'
                );
            }
            const actions = appendText(row, 'div', '', 'saved-source-actions');
            if (source.url && /^https?:\/\//i.test(source.url)) {
                const open = appendText(actions, 'a', 'Open source ↗');
                open.href = source.url;
                open.target = '_blank';
                open.rel = 'noopener noreferrer';
            }
            const remove = appendText(actions, 'button', 'Remove');
            remove.type = 'button';
            remove.addEventListener('click', async () => {
                remove.disabled = true;
                try {
                    await apiJson(`/v1/sources/${encodeURIComponent(record.id)}`, {method: 'DELETE'});
                    await loadHistory();
                } catch (error) {
                    remove.disabled = false;
                    setMessage(reportStatus, error.message, 'error');
                }
            });
            container.appendChild(row);
        });
        byId('sourcePagination').hidden = matches.length <= LIBRARY_PAGE_SIZE;
        byId('sourcePageLabel').textContent = `${sourcesPage + 1} / ${totalPages} · ${matches.length} sources`;
        byId('sourcePrev').disabled = sourcesPage === 0;
        byId('sourceNext').disabled = sourcesPage >= totalPages - 1;
    }

    function makeSourceCard(source, included) {
        const card = document.createElement('article');
        card.className = 'source-item';
        appendText(card, 'strong', source.title || 'Untitled source');
        const meta = [source.authors?.slice?.(0, 2).join(', '), source.year, source.venue || source.journal]
            .filter(Boolean).join(' · ');
        appendText(card, 'p', meta || (included ? 'Included in this review.' : source.exclusion_reason || 'Filtered by the scan.'));
        if (included && source.criteria_result) {
            // Green when it meets every criterion, amber when it is a closest match, always with what it missed.
            appendText(
                card, 'p',
                source.criteria_not_met
                    ? `${source.criteria_result} criteria · not met: ${source.criteria_not_met}`
                    : `${source.criteria_result} criteria`,
                source.criteria_not_met ? 'criteria-chip partial' : 'criteria-chip full'
            );
        }
        if (!included) {
            appendText(card, 'p', `Why excluded: ${source.exclusion_reason || 'Filtered by the scan.'}`, 'source-why');
        }
        if (source.abstract) {
            appendText(card, 'p', cleanDisplayedSourceText(source.abstract).slice(0, 380));
        }
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

    // Free users see a few real rows; the rest is counted and locked, never sent to the browser.
    function lockedRow(hidden, included) {
        const row = document.createElement('div');
        row.className = 'locked-row';
        const text = document.createElement('span');
        text.textContent = `+${hidden} more ${included ? 'included' : 'filtered'} ${hidden === 1 ? 'source' : 'sources'} locked`;
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'button button-cta';
        button.textContent = packButtonLabel();
        button.addEventListener('click', () => openUpgrade('deliverables'));
        row.append(text, button);
        return row;
    }

    function renderEvidencePage(included) {
        const sources = included ? resultIncludedSources : resultExcludedSources;
        const listId = included ? 'includedSources' : 'excludedSources';
        const paginationId = included ? 'includedPagination' : 'excludedPagination';
        const labelId = included ? 'includedPageLabel' : 'excludedPageLabel';
        const previousId = included ? 'includedPrev' : 'excludedPrev';
        const nextId = included ? 'includedNext' : 'excludedNext';
        const totalPages = Math.max(1, Math.ceil(sources.length / RESULT_PAGE_SIZE));
        const currentPage = Math.min(
            included ? includedSourcesPage : excludedSourcesPage,
            totalPages - 1
        );
        if (included) includedSourcesPage = currentPage;
        else excludedSourcesPage = currentPage;

        const start = currentPage * RESULT_PAGE_SIZE;
        const hidden = included ? resultLocked.included : resultLocked.excluded;
        byId(listId).replaceChildren(
            ...sources.slice(start, start + RESULT_PAGE_SIZE).map(source => makeSourceCard(source, included)),
            ...(hidden > 0 ? [lockedRow(hidden, included)] : [])
        );

        const pagination = byId(paginationId);
        pagination.hidden = sources.length <= RESULT_PAGE_SIZE;
        byId(labelId).textContent =
            `Showing ${sources.length ? start + 1 : 0}-${Math.min(start + RESULT_PAGE_SIZE, sources.length)} of ${sources.length}`;
        byId(previousId).disabled = currentPage === 0;
        byId(nextId).disabled = currentPage >= totalPages - 1;
    }

    // Say what the lists are based on, so no list is a black box.
    function renderCriteriaUsed(data) {
        const info = data && data.criteria;
        const line = byId('criteriaUsed');
        if (!info || !Array.isArray(info.applied) || !info.applied.length) {
            line.hidden = true;
            byId('includedBasis').textContent = 'Passed your review criteria';
            byId('excludedBasis').textContent = 'Excluded or below the selected criteria';
            return;
        }
        const count = info.applied.length;
        line.textContent = `Criteria used: ${info.applied.join(' · ')}${info.defaults_applied ? ' (the defaults: you chose none)' : ''}. `
            + (info.strict
                ? 'Strict matching: every criterion is required.'
                : 'Closest matches fill the gap: a source must meet at least half of them, and each one shows what it met and missed.');
        line.hidden = false;
        byId('includedBasis').textContent = info.strict ? `Met all ${count} criteria` : `Met all or most of ${count} criteria`;
        byId('excludedBasis').textContent = `Judged against ${count} ${count === 1 ? 'criterion' : 'criteria'}`;
    }

    function renderResult(data, {scroll = true} = {}) {
        activeResult = data;
        renderCriteriaUsed(data);
        renderUpsells(data);
        renderDeliverables(data);
        track('results_viewed', {
            ...(data.research_run_id ? {run_id: data.research_run_id} : {}),
            included_count: Number(data.counts?.included ?? (Array.isArray(data.included) ? data.included.length : 0)),
            excluded_count: Number(data.counts?.excluded ?? (Array.isArray(data.excluded) ? data.excluded.length : 0)),
            ...(data.ab_variant ? {variant: data.ab_variant} : {})
        });
        restoreCachedReportDownload();
        byId('scanResults').hidden = false;
        const topic = String(data.query || '').trim();
        byId('resultTitle').textContent = topic
            ? topic.replace(/^./u, character => character.toLocaleUpperCase())
            : 'Research evidence';
        resultIncludedSources = Array.isArray(data.included) ? data.included : [];
        resultExcludedSources = Array.isArray(data.excluded) ? data.excluded : [];
        includedSourcesPage = 0;
        excludedSourcesPage = 0;
        // Totals come from the server: a free user's lists are only a preview of them.
        resultTotals = {
            included: Number(data.counts?.included ?? resultIncludedSources.length),
            excluded: Number(data.counts?.excluded ?? resultExcludedSources.length),
        };
        resultLocked = {
            included: Number(data.locked?.included_hidden || 0),
            excluded: Number(data.locked?.excluded_hidden || 0),
        };
        const reviewedCount = resultTotals.included + resultTotals.excluded;
        const resultSummary = byId('resultSummary');
        if (resultSummary) {
            resultSummary.textContent = `${resultTotals.included} sources included · ${resultTotals.excluded} candidates filtered`;
        }
        [
            ['reviewedCount', reviewedCount],
            ['includedCount', resultTotals.included],
            ['excludedCount', resultTotals.excluded]
        ].forEach(([id, count]) => {
            const counter = byId(id);
            if (counter) counter.textContent = String(count);
        });
        renderEvidencePage(true);
        renderEvidencePage(false);
        byId('fullReport').hidden = false;
        setMessage(reportStatus, '');
        if (scroll) byId('scanResults').scrollIntoView({behavior: 'smooth', block: 'start'});
    }

    async function loadRun(runId, options = {}) {
        try {
            const run = await apiJson(`/v1/research/${encodeURIComponent(runId)}`);
            renderResult({...run.result, research_run_id: run.id}, options);
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
        if (!encoded || typeof encoded !== 'string') {
            throw new Error('Report document data is not available.');
        }
        let cleanBase64 = encoded.trim();
        if (cleanBase64.includes(',')) {
            cleanBase64 = cleanBase64.split(',')[1];
        }
        cleanBase64 = cleanBase64.replace(/\s+/g, '');
        while (cleanBase64.length % 4 !== 0) {
            cleanBase64 += '=';
        }
        try {
            const binary = atob(cleanBase64);
            const bytes = new Uint8Array(binary.length);
            for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
            return new Blob([bytes], {type: mimeType});
        } catch (error) {
            throw new Error('The generated report document could not be decoded.');
        }
    }

    const REPORT_CACHE_VERSION = '7';
    let lastReportDownload = null;

    function reportDownloadStorageKey(reportType) {
        const runId = activeResult?.research_run_id;
        return runId ? `nexus-report-download:${runId}:${reportType}` : null;
    }

    function updateReDownloadReportButton() {
        byId('reDownloadReport').hidden = !lastReportDownload;
    }

    function rememberReportDownload(report) {
        lastReportDownload = {
            reportType: report.report_type,
            documentName: report.document_name || 'nexus-research-report.docx',
            documentBase64: report.document_base64,
            cacheId: report.report_cache_id || null,
            cacheVersion: report.report_cache_version || null,
        };
        const storageKey = reportDownloadStorageKey(lastReportDownload.reportType);
        if (storageKey && lastReportDownload.cacheId && lastReportDownload.cacheVersion === REPORT_CACHE_VERSION) {
            sessionStorage.setItem(storageKey, JSON.stringify({
                reportType: lastReportDownload.reportType,
                documentName: lastReportDownload.documentName,
                cacheId: lastReportDownload.cacheId,
                cacheVersion: lastReportDownload.cacheVersion,
            }));
        }
        updateReDownloadReportButton();
    }

    function restoreCachedReportDownload() {
        lastReportDownload = null;
        const runId = activeResult?.research_run_id;
        if (!runId) {
            updateReDownloadReportButton();
            return;
        }
        for (const reportType of ['proposal', 'full_starter']) {
            const stored = sessionStorage.getItem(reportDownloadStorageKey(reportType));
            if (!stored) continue;
            try {
                const report = JSON.parse(stored);
                if (
                    report.cacheId
                    && report.cacheVersion === REPORT_CACHE_VERSION
                    && report.reportType === reportType
                ) {
                    lastReportDownload = report;
                    break;
                }
                sessionStorage.removeItem(reportDownloadStorageKey(reportType));
            } catch (error) {
                sessionStorage.removeItem(reportDownloadStorageKey(reportType));
            }
        }
        updateReDownloadReportButton();
    }

    async function reDownloadLastReport() {
        if (!lastReportDownload) return;
        if (lastReportDownload.cacheVersion !== REPORT_CACHE_VERSION) {
            lastReportDownload = null;
            updateReDownloadReportButton();
            setMessage(reportStatus, 'This cached report is outdated. Generate a new report to download the corrected version.', 'error');
            return;
        }
        const button = byId('reDownloadReport');
        button.disabled = true;
        try {
            const cacheDownloadUrl = `/v1/reports/cache/${encodeURIComponent(lastReportDownload.cacheId)}/download?report_type=${encodeURIComponent(lastReportDownload.reportType)}`;
            await downloadReportDirectly(cacheDownloadUrl, lastReportDownload.documentName);
            setMessage(reportStatus, 'Your previously generated Word report was downloaded.', 'success');
        } catch (error) {
            setMessage(reportStatus, error.message, 'error');
        } finally {
            button.disabled = false;
        }
    }

    async function downloadExcel() {
        if (!activeResult?.research_run_id) return;
        track('deliverable_clicked', {kind: 'excel'});
        byId('downloadExcel').disabled = true;
        setMessage(reportStatus, 'Preparing your Excel dossier…');
        byId('reportStatus').classList.add('status-callout');
        startActivityProgress('excel', [
            'Locating your saved Excel dossier',
            'Preparing the Excel download',
            'Finalizing your dossier file',
        ]);
        try {
            const response = await apiFetch(`/v1/research/${encodeURIComponent(activeResult.research_run_id)}/dossier`);
            if (!response.ok) {
                const body = await response.json().catch(() => ({}));
                const failure = new Error(extractErrorMessage(body, response.status) || `Download failed (${response.status}).`);
                failure.status = response.status;
                failure.payload = body;
                throw failure;
            }
            safeDownload(await response.blob(), activeResult.discovery_report_name || 'research-dossier.xlsx');
            const remaining = response.headers.get('X-Dossier-Downloads-Remaining');
            setMessage(reportStatus, remaining === 'unlimited' || remaining === null
                ? 'Dossier downloaded. Unlimited downloads available.'
                : `Dossier downloaded. ${remaining} free ${remaining === '1' ? 'download' : 'downloads'} remaining.`, 'success');
            finishActivityProgress('excel', 'Excel dossier downloaded.');
            byId('reportStatus').scrollIntoView({behavior: 'smooth', block: 'center'});
        } catch (error) {
            if (error.status === 403) {
                stopActivityProgress('excel');
                byId('excelProgress').hidden = true;
                setMessage(reportStatus, '');
            } else {
                failActivityProgress('excel', 'Excel dossier download stopped before completion.');
                setMessage(reportStatus, error.message, 'error');
            }
            track('error_displayed', {surface: 'download', error_code: 'excel_download_failed', ...(error.status ? {status_code: error.status} : {})});
            if (error.status === 403) {
                const locked = error.payload?.detail?.error_code === 'upgrade_required';
                showUpgradePrompt(byId('reportUpgrade'), {
                    headline: locked ? 'Unlock the full Excel dossier' : 'Download limit reached',
                    description: locked
                        ? error.message
                        : 'A Research Pack removes the limit on Excel audit and Word report downloads.',
                    placement: 'excel_quota',
                });
            }
        } finally {
            byId('downloadExcel').disabled = false;
        }
    }

    const activityProgressTimers = {};

    function setActivityProgress(activity, percent, label) {
        const normalizedPercent = Math.min(100, Math.max(0, Math.round(percent)));
        const progress = byId(`${activity}Progress`);
        const ring = byId(`${activity}ProgressRing`);
        ring.style.setProperty('--report-progress', `${normalizedPercent}%`);
        ring.setAttribute('aria-valuenow', String(normalizedPercent));
        byId(`${activity}ProgressPercent`).textContent = `${normalizedPercent}%`;
        byId(`${activity}ProgressLabel`).textContent = label;
        progress.hidden = false;
    }

    function stopActivityProgress(activity) {
        if (activityProgressTimers[activity] !== undefined) {
            clearInterval(activityProgressTimers[activity]);
            delete activityProgressTimers[activity];
        }
    }

    function startActivityProgress(activity, stages) {
        stopActivityProgress(activity);
        const progress = byId(`${activity}Progress`);
        progress.classList.remove('is-error', 'is-complete');
        const startedAt = Date.now();
        const update = () => {
            const elapsedSeconds = (Date.now() - startedAt) / 1000;
            const percent = Math.min(92, 8 + Math.sqrt(elapsedSeconds) * 10);
            const stage = Math.min(
                stages.length - 1,
                Math.floor(elapsedSeconds / 12),
            );
            setActivityProgress(activity, percent, stages[stage]);
        };
        update();
        activityProgressTimers[activity] = setInterval(update, 1000);
    }

    function finishActivityProgress(activity, label) {
        stopActivityProgress(activity);
        const progress = byId(`${activity}Progress`);
        progress.classList.remove('is-error');
        progress.classList.add('is-complete');
        setActivityProgress(activity, 100, label);
    }

    function failActivityProgress(activity, label) {
        stopActivityProgress(activity);
        const progress = byId(`${activity}Progress`);
        progress.classList.remove('is-complete');
        progress.classList.add('is-error');
        byId(`${activity}ProgressLabel`).textContent = label;
    }

    let reportProgressTimer = null;

    function setReportProgress(percent, label) {
        const normalizedPercent = Math.min(100, Math.max(0, Math.round(percent)));
        const progress = byId('reportProgress');
        const ring = byId('reportProgressRing');
        ring.style.setProperty('--report-progress', `${normalizedPercent}%`);
        ring.setAttribute('aria-valuenow', String(normalizedPercent));
        byId('reportProgressPercent').textContent = `${normalizedPercent}%`;
        byId('reportProgressLabel').textContent = label;
        progress.hidden = false;
    }

    function stopReportProgress() {
        if (reportProgressTimer !== null) {
            clearInterval(reportProgressTimer);
            reportProgressTimer = null;
        }
    }

    function startReportProgress(reportType) {
        stopReportProgress();
        const progress = byId('reportProgress');
        progress.classList.remove('is-error', 'is-complete');
        const startedAt = Date.now();
        const reportName = reportType === 'full_starter' ? 'literature review' : 'proposal report';
        const update = () => {
            const elapsedSeconds = (Date.now() - startedAt) / 1000;
            const percent = Math.min(92, 8 + Math.sqrt(elapsedSeconds) * 10);
            const label = elapsedSeconds < 8
                ? `Preparing evidence for your ${reportName}`
                : elapsedSeconds < 30
                    ? `Drafting your ${reportName}`
                    : 'Validating the synthesis and formatting your document';
            setReportProgress(percent, label);
        };
        update();
        reportProgressTimer = setInterval(update, 1000);
    }

    function finishReportProgress(label) {
        stopReportProgress();
        const progress = byId('reportProgress');
        progress.classList.remove('is-error');
        progress.classList.add('is-complete');
        setReportProgress(100, label);
    }

    function failReportProgress() {
        stopReportProgress();
        const progress = byId('reportProgress');
        progress.classList.remove('is-complete');
        progress.classList.add('is-error');
        byId('reportProgressLabel').textContent = 'Report generation stopped before completion.';
    }

    async function downloadReportDirectly(downloadUrl, filename) {
        const response = await apiFetch(downloadUrl);
        if (!response.ok) {
            const errJson = await response.json().catch(() => ({}));
            throw new Error(extractErrorMessage(errJson, response.status) || `Report download failed (${response.status}).`);
        }
        const blob = await response.blob();
        safeDownload(blob, filename || 'nexus-research-report.docx');
    }

    async function pollReportJob(jobId, runReference, reportType) {
        const maxAttempts = 60;
        const intervalMs = 2500;

        for (let attempt = 0; attempt < maxAttempts; attempt++) {
            await new Promise(resolve => setTimeout(resolve, intervalMs));
            
            const statusResponse = await apiFetch(`/v1/reports/${encodeURIComponent(jobId)}/status`);
            if (!statusResponse.ok) {
                const errJson = await statusResponse.json().catch(() => ({}));
                throw new Error(extractErrorMessage(errJson, statusResponse.status) || 'Failed to check report status.');
            }

            const job = await statusResponse.json();

            if (job.status === 'completed' || job.status === 'ready') {
                const downloadUrl = job.download_url || `/v1/reports/${encodeURIComponent(jobId)}/download`;
                const filename = job.document_name || `${reportType}-report.docx`;
                await downloadReportDirectly(downloadUrl, filename);
                return job;
            }

            if (job.status === 'failed') {
                const failureErr = new Error(job.error_message || job.error_reason || 'Report generation could not be completed.');
                failureErr.jobId = jobId;
                throw failureErr;
            }

            // Update UI progress while waiting
            const progressPercent = Math.min(95, 30 + Math.floor((attempt / maxAttempts) * 65));
            setReportProgress(progressPercent, `Synthesizing report… (${job.estimated_wait || 'in queue'})`);
        }

        const timeoutErr = new Error('Report synthesis timed out. Your request is queued and will be ready shortly.');
        timeoutErr.jobId = jobId;
        throw timeoutErr;
    }

    // Built with DOM nodes and CSS classes: the site CSP (style-src 'self') blocks inline styles,
    // and the reference can originate from a server response, so it is never parsed as HTML.
    function showReportError(title, message, reference, tone) {
        if (!reportStatus) return;
        setMessage(reportStatus, '', tone);
        reportStatus.hidden = false;
        const heading = document.createElement('strong');
        heading.className = 'status-title';
        heading.textContent = title;
        const body = document.createElement('span');
        body.className = 'status-body';
        body.textContent = message;
        const ref = document.createElement('span');
        ref.className = 'status-ref';
        ref.append('Reference ID: ');
        const code = document.createElement('code');
        code.textContent = String(reference || '');
        ref.append(code);
        const help = document.createElement('a');
        help.className = 'status-help';
        help.href = supportLink(`an error (reference ID ${String(reference || 'unknown').slice(0, 64)})`);
        help.target = '_blank';
        help.rel = 'noopener noreferrer';
        help.dataset.support = 'report_error';
        help.textContent = 'Chat with support on WhatsApp';
        reportStatus.append(heading, body, ref, help);
    }

    const FEEDBACK_REASON_IDS = ['inaccurate', 'not_synthesized', 'citations', 'formatting', 'too_long', 'too_short'];
    let feedbackTarget = null;

    function hideFeedback() {
        feedbackTarget = null;
        const panel = byId('reportFeedback');
        if (panel) panel.hidden = true;
    }

    function offerFeedback(reference, reportType) {
        const panel = byId('reportFeedback');
        if (!panel || !reference) return hideFeedback();
        feedbackTarget = {reference, reportType};
        byId('feedbackPrompt').textContent = 'Was this report useful?';
        byId('feedbackChoices').hidden = false;
        byId('feedbackReasons').hidden = true;
        FEEDBACK_REASON_IDS.forEach(id => { byId(`reason_${id}`).checked = false; });
        panel.hidden = false;
    }

    async function submitFeedback(rating) {
        if (!feedbackTarget) return;
        const reasons = rating === 'down'
            ? FEEDBACK_REASON_IDS.filter(id => byId(`reason_${id}`).checked)
            : [];
        const target = feedbackTarget;
        try {
            await apiJson('/v1/feedback', {
                method: 'POST',
                body: JSON.stringify({reference: target.reference, rating, reasons, report_type: target.reportType})
            });
            byId('feedbackPrompt').textContent = 'Thank you. Your feedback helps us improve the reports.';
        } catch (error) {
            byId('feedbackPrompt').textContent = 'Feedback could not be sent. You can try again.';
            return;
        }
        byId('feedbackChoices').hidden = true;
        byId('feedbackReasons').hidden = true;
        feedbackTarget = null;
    }

    function wireFeedback() {
        byId('feedbackUp').addEventListener('click', () => submitFeedback('up'));
        byId('feedbackDown').addEventListener('click', () => {
            byId('feedbackChoices').hidden = true;
            byId('feedbackPrompt').textContent = 'What could be better? (optional)';
            byId('feedbackReasons').hidden = false;
        });
        byId('feedbackSend').addEventListener('click', () => submitFeedback('down'));
    }

    async function generateReport(reportType) {
        if (!activeResult) return;
        if (reportType === 'full_starter' && !paid) {
            openUpgrade('report_locked');
            return;
        }
        const button = reportType === 'full_starter' ? byId('fullReport') : byId('proposalReport');
        track('deliverable_clicked', {kind: reportType});
        hideFeedback();
        hideUpgradePrompts();
        button.disabled = true;
        setMessage(reportStatus, 'Preparing your Word report…');
        byId('reportStatus').classList.add('status-callout');
        startReportProgress(reportType);
        
        const runRef = activeResult.research_run_id || (Math.random().toString(36).substring(2, 10));

        try {
            const reportResponse = await apiJson('/v1/reports', {
                method: 'POST',
                body: JSON.stringify({
                    topic: activeResult.query || byId('topic').value.trim(),
                    included_sources: activeResult.included || [],
                    ...(activeResult.research_run_id ? {research_run_id: activeResult.research_run_id} : {}),
                    report_type: reportType,
                    domain: byId('domain').value,
                    max_sources: Number(byId('maxSources').value)
                })
            });

            const jobId = reportResponse.job_id || reportResponse.report_id || reportResponse.id;
            const filename = reportResponse.document_name || `${reportType}-report.docx`;

            // If immediate download is ready
            if (reportResponse.status === 'ready' || reportResponse.status === 'success' || reportResponse.action === 'docx_generation_complete' || reportResponse.action === 'cached_docx_download') {
                const downloadUrl = reportResponse.download_url || (reportResponse.report_cache_id ? `/v1/reports/cache/${encodeURIComponent(reportResponse.report_cache_id)}/download?report_type=${reportType}` : null);
                
                if (downloadUrl) {
                    await downloadReportDirectly(downloadUrl, filename);
                } else if (reportResponse.document_base64) {
                    safeDownload(
                        base64ToBlob(reportResponse.document_base64, 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'),
                        filename
                    );
                }

                rememberReportDownload(reportResponse);

                if (reportResponse.degraded) {
                    finishReportProgress('Limited evidence-grounded fallback downloaded.');
                    setMessage(
                        reportStatus,
                        `Limited evidence-grounded fallback downloaded. ${reportResponse.synthesis_note || 'It was created from validated source metadata because AI providers are temporarily at capacity.'} Your Excel dossier is unaffected.`,
                        'error'
                    );
                } else {
                    finishReportProgress('Report ready and downloaded.');
                    setMessage(reportStatus, 'Your Word report is ready and downloaded.', 'success');
                }
                offerFeedback(reportResponse.reference, reportType);
                byId('reportStatus').scrollIntoView({behavior: 'smooth', block: 'center'});
                return;
            }

            // If job is queued or in-progress, poll for completion
            if (reportResponse.status === 'queued' || reportResponse.action === 'report_queued_pending' || jobId) {
                setMessage(
                    reportStatus,
                    reportResponse.message || 'Report synthesis request queued. Generating document…',
                    'info'
                );
                
                const completedJob = await pollReportJob(jobId, runRef, reportType);
                rememberReportDownload(completedJob);
                finishReportProgress('Report ready and downloaded.');
                setMessage(reportStatus, 'Your Word report was synthesized and downloaded.', 'success');
                byId('reportStatus').scrollIntoView({behavior: 'smooth', block: 'center'});
                return;
            }

            throw new Error(reportResponse.message || 'Report could not be generated.');

        } catch (error) {
            const errorDetail = (error.payload && error.payload.detail) || error.payload || {};
            if (error.status === 403 && errorDetail.error_code === 'upgrade_required') {
                // Not a failure: the full document needs a pack. Show the offer instead of an error card.
                stopReportProgress();
                byId('reportProgress').hidden = true;
                setMessage(reportStatus, '');
                showUpgradePrompt(byId('reportUpgrade'), {
                    headline: 'Unlock the full Word proposal',
                    description: errorDetail.message || 'The full Word proposal is included with a Research Pack.',
                    placement: 'report_locked',
                });
                return;
            }
            failReportProgress();
            const reference = errorDetail.reference || error.jobId || runRef;
            const errorCode = errorDetail.error_code || 'unknown';

            // Build error display
            let errorTitle = "Report could not be generated";
            let errorMessage = "The report generation service encountered an issue. Your Excel dossier was completed successfully.";
            let statusClass = 'error';

            if (errorCode === 'quota_daily') {
                statusClass = 'warning';
                errorTitle = "Daily quota reached";
                errorMessage = "The synthesis service has reached its daily limit. Please try again tomorrow.";
            } else if (errorCode === 'unavailable') {
                statusClass = 'warning';
                errorTitle = "Service temporarily busy";
                errorMessage = "The report service is at capacity. Try again in a few minutes.";
            } else if (errorCode === 'report_incomplete') {
                statusClass = 'warning';
                errorTitle = "Literature review not finished";
                errorMessage = "We could not finish this literature review. Nothing was lost; please try again in a moment.";
            } else if (errorCode === 'auth' || errorCode === 'config') {
                errorTitle = "Service error";
                errorMessage = "A configuration issue occurred. Contact support if this persists.";
            }

            showReportError(errorTitle, errorMessage, reference, statusClass);
            track('error_displayed', {
                surface: 'report',
                error_code: String(errorCode).slice(0, 60),
                reference_id: String(reference).slice(0, 64),
                ...(error.status ? {status_code: error.status} : {})
            });
        } finally {
            button.disabled = false;
        }
    }

    // "5 of 18 candidates met all 3 criteria" so the user sees what their choices did, and why a strict choice returned few.
    function criteriaNote(data) {
        const info = data && data.criteria;
        if (!info || !Array.isArray(info.applied) || !info.applied.length) return '';
        const checked = Number(info.candidates_checked);
        const meeting = Number(info.candidates_meeting_all);
        const closest = Number(info.closest_matches_included) || 0;
        let note = '';
        if (Number.isFinite(checked) && checked > 0 && Number.isFinite(meeting)) {
            note = ` ${meeting} of ${checked} candidates met ${info.applied.length === 1 ? 'your criterion' : `all ${info.applied.length} criteria`}`
                + `${info.defaults_applied ? ' (the defaults: cited, recent, and unique and topic-relevant)' : ''}.`;
            if (closest > 0) note += ` ${closest} closest ${closest === 1 ? 'match was' : 'matches were'} added; each met at least half and shows what it missed.`;
            if (meeting === 0 && closest === 0) {
                note += info.strict
                    ? ' Try selecting fewer criteria, or switch off "Require every selected criterion".'
                    : ' No candidates met at least half of your criteria. Try selecting fewer criteria.';
            }
        }
        if (info.limited) note += ` Your plan applies up to ${info.limit} criteria; the others were left out.`;
        return note;
    }

    async function runScan(event) {
        event.preventDefault();
        hideUpgradePrompts();
        const topic = byId('topic').value.trim();
        if (!topic) return;
        const button = byId('scanSubmit');
        button.disabled = true;
        setMessage(scanStatus, 'Searching sources and reviewing evidence…');
        byId('scanStatus').classList.add('status-callout');
        startActivityProgress('scan', [
            'Discovering relevant sources',
            'Reviewing evidence quality',
            'Synthesizing your research results',
        ]);
        try {
            const data = await apiJson('/v1/scan', {
                method: 'POST',
                body: JSON.stringify({
                    topic,
                    max_sources: Number(byId('maxSources').value),
                    domain: byId('domain').value,
                    selected_inclusion_reasons: [...document.querySelectorAll('.criteria-fieldset input:checked')]
                        .map(input => input.value),
                    source_type: byId('sourceType').value === 'any' ? null : byId('sourceType').value,
                    strict_criteria: byId('strictCriteria').checked,
                    uploaded_sources: []
                })
            });
            renderResult(data);
            finishActivityProgress('scan', 'Evidence scan complete.');
            setMessage(scanStatus, `Scan complete.${criteriaNote(data)} Your research was saved to your account.`, 'success');
            await loadHistory();
            refreshEntitlement().catch(() => {});
        } catch (error) {
            const limit = error.payload?.detail;
            const limitReached = error.status === 403 && (limit?.requires_bundle || limit?.paywall);
            if (limitReached) {
                // Hitting the limit is not a failed scan: the upsell below carries the message.
                stopActivityProgress('scan');
                byId('scanProgress').hidden = true;
                setMessage(scanStatus, '');
            } else {
                failActivityProgress('scan', 'Evidence scan stopped before completion.');
                setMessage(scanStatus, error.message, 'error');
            }
            track('error_displayed', {
                surface: 'scan',
                error_code: String(error.payload?.detail?.error_code || 'scan_failed').slice(0, 60),
                ...(error.status ? {status_code: error.status} : {})
            });
            if (limitReached) {
                showUpgradePrompt(byId('scanUpgrade'), {
                    headline: limit.paywall?.headline || 'Unlock more scans',
                    description: limit.message || 'You have reached your scan limit.',
                    placement: 'scan_limit',
                });
                byId('scanUpgrade').scrollIntoView({behavior: 'smooth', block: 'nearest'});
            }
            updateUpgradeButton();
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
            plan = null;
            scansRemaining = null;
            setPlanNotice('');
            renderAuthState();
            byId('historyList').replaceChildren();
            byId('savedSourcesList').replaceChildren();
            byId('scanResults').hidden = true;
        }
    }

    // The publication-type selector counts as one criterion when it is set to anything but "Any type".
    function criteriaCount() {
        return document.querySelectorAll('.criteria-fieldset input:checked').length
            + (byId('sourceType').value !== 'any' ? 1 : 0);
    }

    function handleCriteriaLimit(event) {
        const max = paid ? PAID_MAX_CRITERIA : FREE_MAX_CRITERIA;
        if (criteriaCount() <= max) return;
        if (event.target instanceof HTMLInputElement) event.target.checked = false;
        else if (event.target instanceof HTMLSelectElement) event.target.value = 'any';
        setMessage(scanStatus, paid
            ? `You can select up to ${PAID_MAX_CRITERIA} evidence criteria.`
            : `Free accounts can select up to ${FREE_MAX_CRITERIA} criteria. Upgrade to select up to ${PAID_MAX_CRITERIA}.`, 'error');
        byId('scanStatus').classList.add('status-callout', 'limit-callout');
        updateUpgradeButton();
        byId('scanStatus').scrollIntoView({behavior: 'smooth', block: 'center'});
    }

    // The message is prefilled with what the user is looking at (a reference or order id they already
    // see), never an email address or other personal data. They can edit it before sending.
    function supportLink(context) {
        return `https://wa.me/${SUPPORT_WHATSAPP}?text=${encodeURIComponent(`Hi Nexus support, I need help with ${context}.`)}`;
    }

    function setPlanHelp(context, placement) {
        const link = byId('planHelp');
        link.href = supportLink(context);
        link.dataset.support = placement;
    }

    function sendContactEmail(event) {
        event.preventDefault();
        const subject = `Nexus Research AI support — ${byId('contactName').value.trim()}`;
        const body = [
            `Name: ${byId('contactName').value.trim()}`,
            `Email: ${byId('contactEmail').value.trim()}`,
            '',
            byId('contactMessage').value.trim()
        ].join('\n');
        window.location.href = `mailto:${SUPPORT_EMAIL}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
    }

    async function startPackCheckout(packId) {
        const status = byId('billingStatus');
        if (!byId('billingConsent').checked) {
            setMessage(status, 'Please tick the box above to agree to the Terms of Use, then choose your pack.', 'error');
            byId('billingConsent').focus();
            return;
        }
        const buttons = [...document.querySelectorAll('#pricingGrid button[data-pack]')];
        buttons.forEach(button => { button.disabled = true; });
        setMessage(status, 'Opening secure PayPal checkout…');
        try {
            const checkout = await apiJson('/v1/checkout/orders', {method: 'POST', body: JSON.stringify({pack_id: packId})});
            let approval;
            try {
                approval = new URL(checkout.approve_url);
            } catch (error) {
                throw new Error('PayPal did not return a valid secure approval link.');
            }
            if (approval.protocol !== 'https:' ||
                !(approval.hostname === 'paypal.com' || approval.hostname.endsWith('.paypal.com'))) {
                throw new Error('PayPal did not return a valid secure approval link.');
            }
            window.location.assign(approval.toString());
        } catch (error) {
            setMessage(status, error.payload?.detail?.message || error.message, 'error');
            buttons.forEach(button => { button.disabled = false; });
        }
    }

    async function loadPackInfo() {
        try {
            const response = await fetch(`${API_URL}/v1/checkout/packs`);
            if (!response.ok) throw new Error(`pack list ${response.status}`);
            const catalog = await response.json();
            packs = Array.isArray(catalog.packs) ? catalog.packs : [];
            packInfo = packs.find(pack => pack.id === catalog.default) || packs[0] || null;
        } catch (error) {
            packs = [];
            packInfo = null;
        }
        renderPricing();
        renderUpsells(activeResult);
    }

    // PayPal sends the buyer back with ?checkout=complete&token=<order id>. The server verifies the
    // payment with PayPal and credits the pack; this page only reports the result.

    async function finishCheckout(orderId) {
        // The result is written to the plan panel, not the pricing card: it stays visible while the
        // pricing options remain open below it.
        byId('plansCard').hidden = false;
        setMessage(byId('billingStatus'), '');
        setPlanHelp(`my payment (PayPal order ${String(orderId).slice(0, 40)})`, 'payment_status');
        setPlanNotice('Confirming your payment with PayPal…');
        try {
            const result = await apiJson(`/v1/checkout/orders/${encodeURIComponent(orderId)}/capture`, {method: 'POST'});
            await refreshEntitlement();
            // The scan on screen was a preview; now that a pack is active, show the same scan in full.
            if (paid && activeResult && activeResult.preview && activeResult.research_run_id) {
                await loadRun(activeResult.research_run_id, {scroll: false});
            }
            if (result.status === 'pending') {
                setPlanNotice('PayPal is still processing this payment. Your pack unlocks automatically once it clears.', 'success');
            } else {
                const pack = result.pack;
                setPlanNotice(pack
                    ? `Payment confirmed. ${pack.scans} scans were added to your account with the ${pack.name}.`
                    : 'Payment confirmed. Your Research Pack is active.', 'success');
            }
        } catch (error) {
            setPlanNotice(error.payload?.detail?.message || error.message, 'error');
        }
        history.replaceState(null, '', location.pathname);
        byId('workspace').scrollIntoView({behavior: 'smooth', block: 'start'});
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
        loadPackInfo();
        const checkoutResult = new URLSearchParams(location.search).get('checkout');
        try {
            await exchangeCallback();
            await getSession();
            renderAuthState();
            if (session) {
                track('workspace_opened');
                try {
                    await refreshEntitlement();
                } catch (error) {
                    setMessage(scanStatus, error.message, 'error');
                }
                await loadHistory();
                const returnedOrder = new URLSearchParams(location.search).get('token');
                if (checkoutResult === 'complete' && returnedOrder) {
                    await finishCheckout(returnedOrder);
                } else if (checkoutResult === 'cancel') {
                    byId('plansCard').hidden = false;
                    setMessage(byId('billingStatus'), 'Checkout was cancelled. You have not been charged.', 'error');
                    history.replaceState(null, '', location.pathname);
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
        wireFeedback();
        byId('authSignInTab').addEventListener('click', () => setAuthMode('signin'));
        byId('authSignUpTab').addEventListener('click', () => setAuthMode('signup'));
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
        document.querySelector('.criteria-fieldset').addEventListener('change', handleCriteriaLimit);
        byId('historySearch').addEventListener('input', () => { historyPage = 0; renderHistory(); });
        byId('historyDateFilter').addEventListener('change', () => { historyPage = 0; renderHistory(); });
        byId('historyPrev').addEventListener('click', () => { historyPage = Math.max(0, historyPage - 1); renderHistory(); });
        byId('historyNext').addEventListener('click', () => { historyPage += 1; renderHistory(); });
        byId('sourceSearch').addEventListener('input', () => { sourcesPage = 0; renderSavedSources(); });
        byId('sourcePrev').addEventListener('click', () => { sourcesPage = Math.max(0, sourcesPage - 1); renderSavedSources(); });
        byId('sourceNext').addEventListener('click', () => { sourcesPage += 1; renderSavedSources(); });
        byId('includedPrev').addEventListener('click', () => {
            includedSourcesPage = Math.max(0, includedSourcesPage - 1);
            renderEvidencePage(true);
        });
        byId('includedNext').addEventListener('click', () => {
            includedSourcesPage += 1;
            renderEvidencePage(true);
        });
        byId('excludedPrev').addEventListener('click', () => {
            excludedSourcesPage = Math.max(0, excludedSourcesPage - 1);
            renderEvidencePage(false);
        });
        byId('excludedNext').addEventListener('click', () => {
            excludedSourcesPage += 1;
            renderEvidencePage(false);
        });
        byId('contactForm').addEventListener('submit', sendContactEmail);
        document.addEventListener('click', event => {
            const link = event.target.closest('a[data-support]');
            if (link) track('support_chat_clicked', {placement: link.dataset.support});
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
        byId('upgradePlan').addEventListener('click', () => openUpgrade('header'));
        byId('upgradeBannerButton').addEventListener('click', () => openUpgrade('results_banner'));
        byId('deliverablesUpsellButton').addEventListener('click', () => openUpgrade('deliverables'));
        byId('closePlans').addEventListener('click', () => { byId('plansCard').hidden = true; });
        byId('planAddScans').addEventListener('click', () => openUpgrade('header'));
        byId('pricingGrid').addEventListener('click', event => {
            const buy = event.target.closest('button[data-pack]');
            if (buy) {
                startPackCheckout(buy.dataset.pack);
                return;
            }
            if (event.target.closest('button[data-contact]')) {
                track('upgrade_cta_clicked', {placement: 'pricing_contact'});
                byId('contact').scrollIntoView({behavior: 'smooth', block: 'start'});
            }
        });
        byId('stickyUpgradeButton').addEventListener('click', () => openUpgrade('sticky_mobile'));
        window.NexusUI = {
            retryReport: (type) => generateReport(type || 'proposal')
        };
        byId('downloadExcel').addEventListener('click', downloadExcel);
        byId('proposalReport').addEventListener('click', () => generateReport('proposal'));
        byId('fullReport').addEventListener('click', () => generateReport('full_starter'));
        byId('reDownloadReport').addEventListener('click', reDownloadLastReport);
    }

    initialize();
})();
