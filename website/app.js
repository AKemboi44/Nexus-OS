(() => {
    'use strict';

    const SUPABASE_URL = 'https://mdjgrtkjjcwmhuhpsjsk.supabase.co';
    const SUPABASE_PUBLISHABLE_KEY = 'sb_publishable_xp5XQM7DThmmgsVpG4wZog_QVVnOOmw';
    const API_URL = 'https://nexus-os-production-2e14.up.railway.app';
    const SESSION_KEY = 'nexus_web_supabase_session';
    const FREE_MAX_SOURCES = 20;
    const FREE_MAX_CRITERIA = 3;
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
    let authMode = 'signin';
    let activeResult = null;
    let researchRuns = [];
    let savedDossiers = [];
    let savedSources = [];
    let historyPage = 0;
    let sourcesPage = 0;
    let resultIncludedSources = [];
    let resultExcludedSources = [];
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

    async function refreshEntitlement() {
        const response = await apiFetch(`/v1/entitlements/${encodeURIComponent(session.user.id)}`);
        const result = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(extractErrorMessage(result, response.status) || 'Could not refresh subscription status.');
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
        byId('criteriaHint').textContent = paid
            ? 'Choose up to 5 criteria to focus your evidence review.'
            : 'Free accounts can choose up to 3 criteria. Upgrade to select up to 5.';
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
        byId(listId).replaceChildren(
            ...sources.slice(start, start + RESULT_PAGE_SIZE).map(source => makeSourceCard(source, included))
        );

        const pagination = byId(paginationId);
        pagination.hidden = sources.length <= RESULT_PAGE_SIZE;
        byId(labelId).textContent =
            `Showing ${sources.length ? start + 1 : 0}-${Math.min(start + RESULT_PAGE_SIZE, sources.length)} of ${sources.length}`;
        byId(previousId).disabled = currentPage === 0;
        byId(nextId).disabled = currentPage >= totalPages - 1;
    }

    function renderResult(data) {
        activeResult = data;
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
        const reviewedCount = resultIncludedSources.length + resultExcludedSources.length;
        const resultSummary = byId('resultSummary');
        if (resultSummary) {
            resultSummary.textContent = `${resultIncludedSources.length} sources included · ${resultExcludedSources.length} candidates filtered`;
        }
        [
            ['reviewedCount', reviewedCount],
            ['includedCount', resultIncludedSources.length],
            ['excludedCount', resultExcludedSources.length]
        ].forEach(([id, count]) => {
            const counter = byId(id);
            if (counter) counter.textContent = String(count);
        });
        renderEvidencePage(true);
        renderEvidencePage(false);
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
            if (!lastReportDownload.documentBase64) {
                const cached = await apiJson(
                    `/v1/reports/cache/${encodeURIComponent(lastReportDownload.cacheId)}?report_type=${encodeURIComponent(lastReportDownload.reportType)}`
                );
                lastReportDownload.documentBase64 = cached.document_base64;
                lastReportDownload.documentName = cached.document_name;
            }
            safeDownload(
                base64ToBlob(
                    lastReportDownload.documentBase64,
                    'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
                ),
                lastReportDownload.documentName
            );
            setMessage(reportStatus, 'Your previously generated Word report was downloaded.', 'success');
        } catch (error) {
            setMessage(reportStatus, error.message, 'error');
        } finally {
            button.disabled = false;
        }
    }

    async function downloadExcel() {
        if (!activeResult?.research_run_id) return;
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
                const error = await response.json().catch(() => ({}));
                throw new Error(extractErrorMessage(error, response.status) || `Download failed (${response.status}).`);
            }
            safeDownload(await response.blob(), activeResult.discovery_report_name || 'research-dossier.xlsx');
            const remaining = response.headers.get('X-Dossier-Downloads-Remaining');
            setMessage(reportStatus, remaining === 'unlimited'
                ? 'Dossier downloaded. Unlimited downloads available.'
                : `Dossier downloaded. ${remaining} of 3 free downloads remaining.`, 'success');
            finishActivityProgress('excel', 'Excel dossier downloaded.');
            byId('reportStatus').scrollIntoView({behavior: 'smooth', block: 'center'});
        } catch (error) {
            failActivityProgress('excel', 'Excel dossier download stopped before completion.');
            setMessage(reportStatus, error.message, 'error');
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
        byId('reportStatus').classList.add('status-callout');
        startReportProgress(reportType);
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

            if (report.status === 'queued' || report.action === 'report_queued_pending' || (!report.document_base64 && report.message)) {
                finishReportProgress('Report synthesis request queued.');
                setMessage(
                    reportStatus,
                    report.message || 'Report synthesis request queued (usually under 20 minutes). Your report will be available once synthesis completes.',
                    'info'
                );
                byId('reportStatus').scrollIntoView({behavior: 'smooth', block: 'center'});
                return;
            }

            safeDownload(
                base64ToBlob(report.document_base64, 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'),
                report.document_name || 'nexus-research-report.docx'
            );
            rememberReportDownload(report);
            if (report.degraded) {
                finishReportProgress('Limited evidence-grounded fallback downloaded.');
                setMessage(
                    reportStatus,
                    'Limited evidence-grounded fallback downloaded. It is not AI-synthesized and was created only from your validated source metadata and dossier records because all configured AI providers are temporarily quota/rate-limited. It was not saved as an AI report; generate again later for the full AI-synthesized report.',
                    'error'
                );
            } else {
                finishReportProgress('Report ready and downloaded.');
                setMessage(reportStatus, 'Your Word report is ready and downloaded.', 'success');
            }
            byId('reportStatus').scrollIntoView({behavior: 'smooth', block: 'center'});
        } catch (error) {
            failReportProgress();
            setMessage(
                reportStatus,
                error.status === 503
                    ? `${error.message} Your research is still saved; please retry in a few minutes.`
                    : error.message,
                'error'
            );
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
                    uploaded_sources: []
                })
            });
            renderResult(data);
            finishActivityProgress('scan', 'Evidence scan complete.');
            setMessage(scanStatus, 'Scan complete. Your research was saved to your account.', 'success');
            await loadHistory();
        } catch (error) {
            failActivityProgress('scan', 'Evidence scan stopped before completion.');
            setMessage(scanStatus, error.message, 'error');
            if (error.status === 403 || error.payload?.detail?.requires_bundle) {
                if (!paid) byId('upgradePlan').hidden = false;
            }
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

    function handleCriteriaLimit(event) {
        const checked = document.querySelectorAll('.criteria-fieldset input:checked');
        const max = paid ? 5 : FREE_MAX_CRITERIA;
        if (checked.length <= max) return;
        if (event.target instanceof HTMLInputElement) event.target.checked = false;
        setMessage(scanStatus, paid
            ? 'You can select up to 5 evidence criteria.'
            : 'Free accounts can select up to 3 criteria. Upgrade to select up to 5.', 'error');
        byId('scanStatus').classList.add('status-callout', 'limit-callout');
        if (!paid) byId('upgradePlan').hidden = false;
        byId('scanStatus').scrollIntoView({behavior: 'smooth', block: 'center'});
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
        window.location.href = `mailto:support@brisklightai.com?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
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
        byId('whatsappContact').addEventListener('click', () => {
            byId('whatsappHint').textContent = 'WhatsApp support is coming soon. Please use the contact form for now.';
            byId('whatsappHint').classList.add('whatsapp-hint-visible');
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
        byId('reDownloadReport').addEventListener('click', reDownloadLastReport);
    }

    initialize();
})();
