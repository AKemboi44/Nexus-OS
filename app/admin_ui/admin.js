(() => {
    'use strict';

    const TOKEN_KEY = 'nexus_admin_token';
    const SESSION_KEY = 'nexus_admin_session';
    const SUPABASE_URL = 'https://mdjgrtkjjcwmhuhpsjsk.supabase.co';
    const SUPABASE_PUBLISHABLE_KEY = 'sb_publishable_xp5XQM7DThmmgsVpG4wZog_QVVnOOmw';
    const SVG_NS = 'http://www.w3.org/2000/svg';
    const ENVELOPE_KEYS = new Set(['source', 'schema_v', 'request_id', 'app_version', 'exp']);
    const STATUS = {
        good: {label: 'On target', glyph: '✓'},
        warn: {label: 'Watch', glyph: '▲'},
        bad: {label: 'Off target', glyph: '✕'},
        low_sample: {label: 'Low sample', glyph: '○'},
        no_data: {label: 'No data', glyph: '○'},
        info: {label: 'Info', glyph: '○'},
    };
    const state = {days: 30, tab: 'scorecard'};
    const $ = id => document.getElementById(id);

    function el(tag, className, text) {
        const node = document.createElement(tag);
        if (className) node.className = className;
        if (text !== undefined) node.textContent = text;
        return node;
    }

    function svg(tag, attrs = {}) {
        const node = document.createElementNS(SVG_NS, tag);
        Object.entries(attrs).forEach(([key, value]) => node.setAttribute(key, String(value)));
        return node;
    }

    // --- formatting --------------------------------------------------------------------

    function fmt(value, unit) {
        if (value === null || value === undefined || Number.isNaN(value)) return '—';
        switch (unit) {
            case 'rate': return `${(value * 100).toFixed(1)}%`;
            case 'ms': return value >= 1000 ? `${(value / 1000).toFixed(1)} s` : `${Math.round(value)} ms`;
            case 's': return value >= 120 ? `${(value / 60).toFixed(1)} min` : `${Math.round(value)} s`;
            case 'usd': return `$${value.toFixed(value < 1 ? 4 : 2)}`;
            default: return Math.round(value).toLocaleString();
        }
    }

    const BREAKDOWN_UNITS = {p50: null, p95: null, mean: null, median: null, total_usd: 'usd', mean_input: 'tokens', mean_output: 'tokens'};

    function fmtLoose(key, value, unit) {
        const leaf = String(key).split(' / ').pop();
        if (typeof value === 'number' && leaf in BREAKDOWN_UNITS) return fmt(value, BREAKDOWN_UNITS[leaf] || unit);
        if (typeof value === 'number') {
            if (/rate|share/i.test(key)) return `${(value * 100).toFixed(1)}%`;
            return Number.isInteger(value) ? value.toLocaleString() : value.toFixed(3);
        }
        if (value === null || value === undefined) return '—';
        return String(value);
    }

    function deltaNode(metric) {
        if (metric.delta === null || metric.delta === undefined) return null;
        const up = metric.delta > 0;
        const flat = metric.delta === 0;
        const arrow = flat ? '→' : up ? '▲' : '▼';
        const size = metric.unit === 'rate'
            ? `${Math.abs(metric.delta * 100).toFixed(1)} pts`
            : fmt(Math.abs(metric.delta), metric.unit);
        let tone = '';
        if (!flat && metric.good) tone = (up === (metric.good === 'up')) ? ' improve' : ' worsen';
        return el('span', `delta${tone}`, `${arrow} ${size} vs previous`);
    }

    function targetText(metric) {
        if (metric.target === null || metric.target === undefined || !metric.good) return '';
        return `Target ${metric.good === 'up' ? '≥' : '≤'} ${fmt(metric.target, metric.unit)}`;
    }

    function chip(status) {
        const info = STATUS[status] || STATUS.info;
        const node = el('span', `chip ${status}`);
        node.append(el('span', 'glyph', info.glyph), info.label);
        return node;
    }

    // --- API ---------------------------------------------------------------------------

    function readSession() {
        try {
            return JSON.parse(sessionStorage.getItem(SESSION_KEY) || 'null');
        } catch (error) {
            return null;
        }
    }

    function saveSession(session) {
        sessionStorage.setItem(SESSION_KEY, JSON.stringify({
            access_token: session.access_token, refresh_token: session.refresh_token,
        }));
    }

    async function supabase(path, {body, accessToken} = {}) {
        const headers = {apikey: SUPABASE_PUBLISHABLE_KEY, 'Content-Type': 'application/json'};
        if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
        const response = await fetch(`${SUPABASE_URL}/auth/v1/${path}`, {
            method: 'POST', headers, body: JSON.stringify(body || {}),
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            throw new Error(data.msg || data.error_description || data.message || `Sign-in failed (${response.status}).`);
        }
        return data;
    }

    async function refreshSession() {
        const session = readSession();
        if (!session?.refresh_token) return false;
        try {
            saveSession(await supabase('token?grant_type=refresh_token', {body: {refresh_token: session.refresh_token}}));
            return true;
        } catch (error) {
            return false;
        }
    }

    async function api(path, retried = false) {
        const token = sessionStorage.getItem(TOKEN_KEY);
        const session = readSession();
        const headers = {};
        if (token) headers['X-Admin-Token'] = token;
        else if (session) headers.Authorization = `Bearer ${session.access_token}`;
        const response = await fetch(path, {headers});
        if (response.status === 401 && !token && !retried && await refreshSession()) return api(path, true);
        const body = await response.json().catch(() => ({}));
        if (response.status === 401 || response.status === 403) {
            signOut(response.status === 403 && typeof body.detail === 'string' ? body.detail : 'Sign-in not accepted.');
            throw new Error('unauthorized');
        }
        if (!response.ok) throw new Error(typeof body.detail === 'string' ? body.detail : `Request failed (${response.status}).`);
        return body;
    }

    // --- tooltip -----------------------------------------------------------------------

    function showTip(event, text) {
        const tip = $('tooltip');
        tip.textContent = text;
        tip.hidden = false;
        tip.style.left = `${Math.min(event.clientX + 14, window.innerWidth - 280)}px`;
        tip.style.top = `${event.clientY + 14}px`;
    }

    function hideTip() { $('tooltip').hidden = true; }

    // --- charts ------------------------------------------------------------------------

    function sparkline(series) {
        const points = (series || []).filter(p => p.value !== null && p.value !== undefined);
        const box = svg('svg', {class: 'spark', viewBox: '0 0 120 34', role: 'img', 'aria-label': 'Trend over recent days'});
        if (points.length < 2) return box;
        const values = points.map(p => p.value);
        const min = Math.min(...values), max = Math.max(...values);
        const span = max - min || 1;
        const xy = points.map((p, i) => [4 + (i / (points.length - 1)) * 112, max === min ? 17 : 28 - ((p.value - min) / span) * 22]);
        const line = xy.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(' ');
        box.append(
            svg('polygon', {class: 'spark-area', points: `${xy[0][0]},30 ${line} ${xy[xy.length - 1][0]},30`}),
            svg('polyline', {class: 'spark-line', points: line}),
            svg('circle', {class: 'dot', cx: xy[xy.length - 1][0], cy: xy[xy.length - 1][1], r: 4}),
        );
        return box;
    }

    function niceMax(value) {
        if (value <= 0) return 1;
        const power = 10 ** Math.floor(Math.log10(value));
        const n = value / power;
        return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10) * power;
    }

    function lineChart(series, unit) {
        const points = series.filter(p => p.value !== null && p.value !== undefined);
        const W = 580, H = 210, L = 52, R = 56, T = 14, B = 26;
        const box = svg('svg', {class: 'chart', viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': 'Metric by day'});
        if (!points.length) return box;
        const top = unit === 'rate' && Math.max(...points.map(p => p.value)) <= 1
            ? 1 : niceMax(Math.max(...points.map(p => p.value)));
        const x = i => L + (points.length === 1 ? (W - L - R) / 2 : (i / (points.length - 1)) * (W - L - R));
        const y = v => T + (1 - v / top) * (H - T - B);

        [0, 0.5, 1].forEach(fraction => {
            const yy = y(top * fraction);
            box.append(
                svg('line', {class: fraction === 0 ? 'baseline' : 'gridline', x1: L, x2: W - R, y1: yy, y2: yy}),
                Object.assign(svg('text', {class: 'tick', x: L - 6, y: yy + 4, 'text-anchor': 'end'}), {textContent: fraction === 0 ? '0' : fmt(top * fraction, unit)}),
            );
        });
        const first = points[0].date, last = points[points.length - 1].date;
        box.append(
            Object.assign(svg('text', {class: 'tick', x: L, y: H - 6}), {textContent: first}),
            Object.assign(svg('text', {class: 'tick', x: W - R, y: H - 6, 'text-anchor': 'end'}), {textContent: last}),
        );

        const line = points.map((p, i) => `${x(i).toFixed(1)},${y(p.value).toFixed(1)}`).join(' ');
        const baseY = y(0);
        box.append(
            svg('polygon', {class: 'area', points: `${x(0)},${baseY} ${line} ${x(points.length - 1)},${baseY}`}),
            svg('polyline', {class: 'line', points: line}),
        );
        const end = points[points.length - 1];
        box.append(
            svg('circle', {class: 'dot', cx: x(points.length - 1), cy: y(end.value), r: 4}),
            Object.assign(svg('text', {class: 'endlabel', x: x(points.length - 1) + 8, y: y(end.value) + 4}), {textContent: fmt(end.value, unit)}),
        );

        const cross = svg('line', {class: 'crosshair', y1: T, y2: baseY, visibility: 'hidden'});
        const marker = svg('circle', {class: 'dot', r: 4, visibility: 'hidden'});
        const hit = svg('rect', {x: L, y: T, width: W - L - R, height: H - T - B, fill: 'transparent'});
        hit.addEventListener('mousemove', event => {
            const rect = box.getBoundingClientRect();
            const px = ((event.clientX - rect.left) / rect.width) * W;
            const index = points.length === 1 ? 0
                : Math.max(0, Math.min(points.length - 1, Math.round(((px - L) / (W - L - R)) * (points.length - 1))));
            cross.setAttribute('x1', x(index)); cross.setAttribute('x2', x(index));
            cross.setAttribute('visibility', 'visible');
            marker.setAttribute('cx', x(index)); marker.setAttribute('cy', y(points[index].value));
            marker.setAttribute('visibility', 'visible');
            showTip(event, `${points[index].date}: ${fmt(points[index].value, unit)}`);
        });
        hit.addEventListener('mouseleave', () => {
            cross.setAttribute('visibility', 'hidden'); marker.setAttribute('visibility', 'hidden'); hideTip();
        });
        box.append(cross, marker, hit);
        return box;
    }

    function funnelChart(steps) {
        const maxUsers = Math.max(1, ...steps.map(s => s.users));
        const rowHeight = 34, labelWidth = 150, barMax = 300, W = 580;
        const box = svg('svg', {class: 'chart', viewBox: `0 0 ${W} ${steps.length * rowHeight + 6}`, role: 'img', 'aria-label': 'Funnel by step'});
        box.append(svg('line', {class: 'baseline', x1: labelWidth, x2: labelWidth, y1: 0, y2: steps.length * rowHeight}));
        steps.forEach((step, i) => {
            const yy = i * rowHeight + 8;
            const width = Math.max(2, (step.users / maxUsers) * barMax);
            const bar = svg('path', {
                class: 'bar',
                d: `M${labelWidth},${yy} h${width - 4} a4,4 0 0 1 4,4 v12 a4,4 0 0 1 -4,4 h-${width - 4} z`,
            });
            bar.addEventListener('mousemove', event => showTip(event, `${step.label}: ${step.users.toLocaleString()} users`));
            bar.addEventListener('mouseleave', hideTip);
            const note = step.step_rate === null || step.step_rate === undefined ? '' : `  (${(step.step_rate * 100).toFixed(0)}% of previous)`;
            box.append(
                Object.assign(svg('text', {class: 'bar-label', x: labelWidth - 8, y: yy + 15, 'text-anchor': 'end'}), {textContent: step.label}),
                bar,
                Object.assign(svg('text', {class: 'bar-value', x: labelWidth + width + 8, y: yy + 15}), {textContent: `${step.users.toLocaleString()}${note}`}),
            );
        });
        return box;
    }

    // --- generic tables ----------------------------------------------------------------

    function table(headers, rows, numericColumns = []) {
        const wrap = el('div', 'tablewrap');
        const grid = el('table');
        const head = el('tr');
        headers.forEach((h, i) => head.append(el('th', numericColumns.includes(i) ? 'num' : '', h)));
        grid.append(head);
        rows.forEach(cells => {
            const tr = el('tr');
            cells.forEach((cell, i) => {
                const td = el('td', numericColumns.includes(i) ? 'num' : '');
                if (cell instanceof Node) td.append(cell); else td.textContent = cell;
                tr.append(td);
            });
            grid.append(tr);
        });
        wrap.append(grid);
        return wrap;
    }

    function flatten(value, prefix = '', out = []) {
        if (value && typeof value === 'object' && !Array.isArray(value)) {
            Object.entries(value).forEach(([key, inner]) => flatten(inner, prefix ? `${prefix} / ${key}` : key, out));
        } else {
            out.push([prefix, value]);
        }
        return out;
    }

    function breakdownView(breakdown, unit) {
        if (breakdown === null || breakdown === undefined) return null;
        if (Array.isArray(breakdown) && breakdown.every(item => item && 'stage' in item)) return funnelChart(breakdown);
        const rows = flatten(breakdown).map(([key, value]) => [key, fmtLoose(key, value, unit)]);
        return rows.length ? table(['Item', 'Value'], rows, [1]) : null;
    }

    // --- scorecard ---------------------------------------------------------------------

    function metricCard(metric) {
        const card = el('button', 'card');
        card.type = 'button';
        card.append(el('span', 'label', metric.name), el('span', 'value', fmt(metric.value, metric.unit)));
        const meta = el('span', 'meta');
        meta.append(chip(metric.status));
        const delta = deltaNode(metric);
        if (delta) meta.append(delta);
        card.append(meta);
        const target = targetText(metric);
        if (target) card.append(el('span', 'meta', target));
        if (metric.series) card.append(sparkline(metric.series));
        card.addEventListener('click', () => openDetail(metric.id));
        return card;
    }

    async function renderScorecard(view) {
        const data = await api(`/v1/admin/metrics?days=${state.days}`);
        if (!data.events_in_window) showNotice('No events recorded in this window yet. Metrics appear as people use the product.');
        else if (data.data_truncated) showNotice('The window holds more events than the dashboard reads, so the oldest were left out. Pick a shorter window.');
        data.categories.forEach(category => {
            const section = el('section', 'category');
            section.append(el('h2', '', category.name));
            const grid = el('div', 'grid');
            category.metrics.forEach(metric => grid.append(metricCard(metric)));
            section.append(grid);
            view.append(section);
        });
    }

    async function openDetail(id) {
        const panel = $('detail');
        panel.replaceChildren(el('p', 'empty', 'Loading…'));
        panel.hidden = false;
        try {
            const metric = await api(`/v1/admin/metrics/${encodeURIComponent(id)}?days=${state.days}`);
            panel.replaceChildren();
            const close = el('button', 'close', 'Close');
            close.type = 'button';
            close.addEventListener('click', () => { panel.hidden = true; hideTip(); });
            panel.append(close, el('h2', '', metric.name), el('p', 'desc', metric.description));

            const facts = el('div', 'facts');
            const add = (label, text) => { const s = el('span'); s.append(`${label} `, el('strong', '', text)); facts.append(s); };
            add('Value', fmt(metric.value, metric.unit));
            add('Window', `${metric.window_days} days`);
            add('Sample', metric.n.toLocaleString());
            if (metric.numerator !== null && metric.denominator !== null) add('Calculation', `${fmtLoose('', metric.numerator)} of ${fmtLoose('', metric.denominator)}`);
            if (metric.previous !== null) add('Previous period', fmt(metric.previous, metric.unit));
            if (targetText(metric)) add('Goal', targetText(metric));
            const status = el('span'); status.append(chip(metric.status)); facts.append(status);
            panel.append(facts);

            if (metric.series && metric.series.some(p => p.value !== null)) {
                panel.append(el('h3', '', 'By day'));
                const holder = el('div');
                holder.append(lineChart(metric.series, metric.unit));
                const toggle = el('button', 'toggle', 'View as table');
                toggle.type = 'button';
                let asTable = false;
                toggle.addEventListener('click', () => {
                    asTable = !asTable;
                    holder.replaceChildren(asTable
                        ? table(['Date', 'Value'], metric.series.map(p => [p.date, fmt(p.value, metric.unit)]), [1])
                        : lineChart(metric.series, metric.unit));
                    toggle.textContent = asTable ? 'View as chart' : 'View as table';
                });
                panel.append(holder, toggle);
            } else if (metric.series) {
                panel.append(el('p', 'empty', 'No daily values in this window.'));
            }

            const breakdown = breakdownView(metric.breakdown, metric.unit);
            if (breakdown) panel.append(el('h3', '', 'Breakdown'), breakdown);
        } catch (error) {
            if (error.message !== 'unauthorized') panel.replaceChildren(el('p', 'empty', error.message));
        }
    }

    // --- request trace -----------------------------------------------------------------

    function detailsText(properties) {
        return Object.entries(properties)
            .filter(([key, value]) => !ENVELOPE_KEYS.has(key) && value !== null && value !== undefined && value !== '')
            .map(([key, value]) => `${key}=${value}`)
            .join('  ');
    }

    async function renderTrace(view) {
        const form = el('form', 'lookup');
        const input = el('input');
        input.placeholder = 'Reference ID from a user report or error';
        input.setAttribute('aria-label', 'Reference ID');
        input.required = true;
        const submit = el('button', '', 'Look up');
        submit.type = 'submit';
        const results = el('div');
        form.append(input, submit);
        view.append(form, results);
        form.addEventListener('submit', async event => {
            event.preventDefault();
            results.replaceChildren(el('p', 'empty', 'Looking up…'));
            try {
                const trace = await api(`/v1/admin/trace/${encodeURIComponent(input.value.trim())}`);
                results.replaceChildren();
                const pills = el('div', 'pills');
                const pill = text => pills.append(el('span', 'pill', text));
                pill(`${trace.summary.events} events`);
                pill(`${trace.summary.llm_calls} model calls`);
                pill(`${trace.summary.input_tokens.toLocaleString()} input tokens`);
                pill(`${trace.summary.output_tokens.toLocaleString()} output tokens`);
                Object.entries(trace.summary.spans).forEach(([name, ms]) => pill(`${name} ${fmt(ms, 'ms')}`));
                results.append(pills, table(
                    ['Time', 'Source', 'Event', 'Details'],
                    trace.timeline.map(item => [
                        new Date(item.at).toLocaleTimeString(undefined, {hour12: false}) + '.' + String(new Date(item.at).getMilliseconds()).padStart(3, '0'),
                        item.source, item.event, el('span', 'mono', detailsText(item.properties)),
                    ]),
                ));
            } catch (error) {
                if (error.message !== 'unauthorized') results.replaceChildren(el('p', 'empty', error.message));
            }
        });
    }

    // --- instrumentation health --------------------------------------------------------

    async function renderHealth(view) {
        const data = await api('/v1/admin/health?days=7');
        view.append(el('p', 'notice', `Events received in the last ${data.window_days} days, and registered events that have not arrived.`));
        view.append(el('h3', '', 'Events received'));
        view.append(data.events.length
            ? table(['Event', 'Registered', 'Count', 'Last seen', 'Sources', 'Schema problems'],
                data.events.map(e => [e.event, e.registered ? 'Yes' : 'No', e.count.toLocaleString(),
                    new Date(e.last_seen).toLocaleString(),
                    Object.entries(e.sources).map(([s, n]) => `${s} ${n}`).join(', '),
                    String(e.schema_problems)]), [2, 5])
            : el('p', 'empty', 'No events received yet.'));
        view.append(el('h3', '', 'Registered but never seen'));
        view.append(data.never_seen.length
            ? table(['Event', 'Expected from', 'Stage'], data.never_seen.map(e => [e.event, e.expected_from.join(', '), e.stage]))
            : el('p', 'empty', 'Every registered event has arrived.'));
        if (data.unregistered.length) {
            view.append(el('h3', '', 'Unregistered events'), el('p', 'mono', data.unregistered.join(', ')));
        }
    }

    // --- shell -------------------------------------------------------------------------

    const TABS = [
        {id: 'scorecard', label: 'Scorecard', render: renderScorecard},
        {id: 'trace', label: 'Request trace', render: renderTrace},
        {id: 'health', label: 'Instrumentation health', render: renderHealth},
    ];

    function showNotice(text) {
        const notice = $('notice');
        notice.textContent = text;
        notice.hidden = !text;
    }

    async function render() {
        const view = $('view');
        showNotice('');
        view.replaceChildren(el('p', 'empty', 'Loading…'));
        const tab = TABS.find(t => t.id === state.tab) || TABS[0];
        const next = el('div');
        try {
            await tab.render(next);
            view.replaceChildren(next);
        } catch (error) {
            if (error.message !== 'unauthorized') view.replaceChildren(el('p', 'empty', error.message));
        }
    }

    function renderTabs() {
        const nav = $('tabs');
        nav.replaceChildren();
        TABS.forEach(tab => {
            const button = el('button', '', tab.label);
            button.type = 'button';
            button.setAttribute('role', 'tab');
            button.setAttribute('aria-selected', String(tab.id === state.tab));
            button.addEventListener('click', () => { state.tab = tab.id; $('detail').hidden = true; renderTabs(); render(); });
            nav.append(button);
        });
    }

    // A filled green dot means real money (live); a hollow amber ring means test money (sandbox).
    const MODE_TEXT = {live: 'PayPal live', sandbox: 'PayPal sandbox', not_configured: 'PayPal not set up'};

    async function renderMode() {
        const badge = $('modeBadge');
        const notice = $('modeNotice');
        try {
            const {paypal} = await api('/v1/admin/status');
            const mode = MODE_TEXT[paypal.mode] ? paypal.mode : 'not_configured';
            badge.className = `mode-badge ${mode}`;
            $('modeText').textContent = MODE_TEXT[mode];
            badge.title = mode === 'live' ? 'Buyers are charged real money.'
                : mode === 'sandbox' ? 'Test mode: no real money moves.' : 'PayPal credentials are not set on the server.';
            badge.hidden = false;
            notice.textContent = (paypal.warnings || []).join(' ');
            notice.hidden = !notice.textContent;
        } catch (error) {
            badge.hidden = true;
            notice.hidden = true;
        }
    }

    function showApp() {
        $('login').hidden = true;
        $('app').hidden = false;
        $('controls').hidden = false;
        renderTabs();
        render();
        renderMode();
    }

    function showForm(name) {
        ['loginForm', 'mfaForm', 'tokenForm'].forEach(id => { $(id).hidden = id !== name; });
        $('loginMessage').textContent = '';
    }

    function signOut(message = '') {
        sessionStorage.removeItem(TOKEN_KEY);
        sessionStorage.removeItem(SESSION_KEY);
        pending = null;
        $('app').hidden = true;
        $('controls').hidden = true;
        $('modeNotice').hidden = true;
        $('detail').hidden = true;
        $('login').hidden = false;
        ['emailInput', 'passwordInput', 'tokenInput', 'mfaCode'].forEach(id => { $(id).value = ''; });
        showForm('loginForm');
        $('loginMessage').textContent = message;
    }

    // The password sign-in only reaches the dashboard once a one-time code has upgraded the session.
    let pending = null;

    async function beginEnrollment() {
        const enrolment = await supabase('factors', {
            accessToken: pending.accessToken,
            body: {factor_type: 'totp', friendly_name: `Nexus admin ${Date.now()}`},
        });
        pending.factorId = enrolment.id;
        $('mfaPrompt').textContent = 'Scan this code with an authenticator app, then enter the 6-digit code it shows.';
        $('mfaQr').src = enrolment.totp.qr_code;
        $('mfaQr').hidden = false;
        $('mfaSecret').textContent = `Manual key: ${enrolment.totp.secret}`;
        $('mfaSecret').hidden = false;
        showForm('mfaForm');
    }

    $('loginForm').addEventListener('submit', async event => {
        event.preventDefault();
        $('loginSubmit').disabled = true;
        try {
            const result = await supabase('token?grant_type=password', {
                body: {email: $('emailInput').value.trim(), password: $('passwordInput').value},
            });
            pending = {accessToken: result.access_token};
            const factor = (result.user?.factors || []).find(f => f.factor_type === 'totp' && f.status === 'verified');
            if (factor) {
                pending.factorId = factor.id;
                $('mfaPrompt').textContent = 'Enter the 6-digit code from your authenticator app.';
                $('mfaQr').hidden = true;
                $('mfaSecret').hidden = true;
                showForm('mfaForm');
            } else {
                await beginEnrollment();
            }
        } catch (error) {
            pending = null;
            $('loginMessage').textContent = error.message;
        } finally {
            $('loginSubmit').disabled = false;
        }
    });

    $('mfaForm').addEventListener('submit', async event => {
        event.preventDefault();
        $('mfaSubmit').disabled = true;
        try {
            const challenge = await supabase(`factors/${pending.factorId}/challenge`, {accessToken: pending.accessToken});
            const session = await supabase(`factors/${pending.factorId}/verify`, {
                accessToken: pending.accessToken,
                body: {challenge_id: challenge.id, code: $('mfaCode').value.trim()},
            });
            saveSession(session);
            pending = null;
            $('mfaCode').value = '';
            showApp();
        } catch (error) {
            $('loginMessage').textContent = error.message;
        } finally {
            $('mfaSubmit').disabled = false;
        }
    });

    $('tokenForm').addEventListener('submit', event => {
        event.preventDefault();
        sessionStorage.setItem(TOKEN_KEY, $('tokenInput').value.trim());
        showApp();
    });
    $('useTokenBtn').addEventListener('click', () => showForm('tokenForm'));
    $('usePasswordBtn').addEventListener('click', () => showForm('loginForm'));
    $('signOut').addEventListener('click', () => signOut());
    $('refresh').addEventListener('click', () => { render(); renderMode(); });
    $('windowPicker').addEventListener('click', event => {
        const button = event.target.closest('button[data-days]');
        if (!button) return;
        state.days = Number(button.dataset.days);
        $('windowPicker').querySelectorAll('button').forEach(b => b.setAttribute('aria-pressed', String(b === button)));
        render();
    });

    if (sessionStorage.getItem(TOKEN_KEY) || readSession()) showApp();
})();
