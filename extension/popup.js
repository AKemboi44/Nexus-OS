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
    const proPlanOption = document.getElementById('proPlanOption');
    const ultimatePlanOption = document.getElementById('ultimatePlanOption');
    const checkoutPlanName = document.getElementById('checkoutPlanName');
    const checkoutSourceCapacity = document.getElementById('checkoutSourceCapacity');
    const checkoutDomainCapacity = document.getElementById('checkoutDomainCapacity');
    const checkoutPlanPrice = document.getElementById('checkoutPlanPrice');
    const termsAgreement = document.getElementById('termsAgreement');
    const termsLinkBtn = document.getElementById('termsLinkBtn');
    const backToCheckoutBtn = document.getElementById('backToCheckoutBtn');
    const acceptTermsBtn = document.getElementById('acceptTermsBtn');
    const retryBtn = document.getElementById('retryBtn');
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
    const sProgContainer = document.getElementById('scribeProgressContainer');
    const sProgressBar = document.getElementById('scribeProgressBar');
    const sStep1 = document.getElementById('sStep1'); const sStep2 = document.getElementById('sStep2');
    const sStep3 = document.getElementById('sStep3'); const sStep4 = document.getElementById('sStep4');

    const FREE_LIMIT = 5;

    let activeSessionIncludedPapers = [];
    let activeSessionExcludedPapers = [];
    let lastRequestContext = null;
    let activeReportButton = null;
    let activeReportType = null;
    let reportGenerationCancelled = false;
    let reportProcessingActive = false;
    let selectedPlan = 'pro';
    const manifest = chrome.runtime.getManifest();
    const isLocalTestingInstall = !manifest.update_url;
    const isBrowserWhitelisted = isLocalTestingInstall;

    function setAuthStatus(message, type = 'error') {
        if (!authStatus) return;
        authStatus.textContent = message;
        authStatus.className = `auth-status ${type}`;
        authStatus.style.display = 'block';
    }

    function setSignedInState(user) {
        const signedIn = isBrowserWhitelisted || Boolean(user?.email);
        document.body.classList.toggle('auth-locked', !signedIn);
        if (authGate) authGate.hidden = signedIn && !isBrowserWhitelisted;
        if (signupTermsScreen && signedIn) signupTermsScreen.style.display = 'none';
        if (authPreviewSurface) {
            authPreviewSurface.setAttribute('aria-hidden', String(!signedIn));
            authPreviewSurface.inert = !signedIn;
        }
        if (signedInBadge) {
            signedInBadge.style.display = signedIn ? 'block' : 'none';
            signedInBadge.textContent = isBrowserWhitelisted && !user?.email
                ? 'Local browser testing enabled'
                : `Signed in as ${user.email}`;
        }
    }

    async function loadAuthState() {
        const stored = await chrome.storage.local.get(['nexus_auth_user']);
        setSignedInState(stored.nexus_auth_user);
    }

    signupForm?.addEventListener('submit', async event => {
        event.preventDefault();
        const email = signupEmail?.value.trim().toLowerCase();
        const password = signupPassword?.value || '';
        if (!signupForm.checkValidity() || !email || password.length < 8 || !signupTerms?.checked) {
            setAuthStatus('Enter a valid email, use at least 8 characters for your password, and accept the terms.');
            signupForm.reportValidity();
            return;
        }
        const user = {
            email,
            provider: 'email',
            createdAt: new Date().toISOString()
        };
        await chrome.storage.local.set({ nexus_auth_user: user });
        setAuthStatus('Account created. Your research workspace is now available.', 'success');
        setSignedInState(user);
    });

    googleSignupBtn?.addEventListener('click', () => {
        if (!chrome.identity?.getProfileUserInfo) {
            setAuthStatus('Google signup is unavailable in this browser context. Use email signup or enable the Identity permission.');
            return;
        }
        chrome.identity.getProfileUserInfo(async profile => {
            if (chrome.runtime.lastError) {
                setAuthStatus(`Google signup could not start: ${chrome.runtime.lastError.message}`);
                return;
            }
            if (!profile?.email) {
                setAuthStatus('Sign in to Chrome with a Google account, then try Google signup again.');
                return;
            }
            const user = {
                email: profile.email.toLowerCase(),
                provider: 'google',
                createdAt: new Date().toISOString()
            };
            await chrome.storage.local.set({ nexus_auth_user: user });
            setAuthStatus('Google account connected. Your research workspace is now available.', 'success');
            setSignedInState(user);
        });
    });

    loadAuthState();

    // Unpacked developer installs are whitelisted so local testing is not blocked.
    let isPaidUser = isLocalTestingInstall;

    const mainSurface = [
        banner,
        accessCard,
        document.querySelector('.tabs-nav'),
        ...document.querySelectorAll('.tab-content')
    ];

    function showUpgradeFlow(screen = 'details') {
        mainSurface.forEach(element => {
            if (element) element.style.display = 'none';
        });
        if (upgradeFlow) upgradeFlow.style.display = 'block';
        if (upgradeDetailsScreen) upgradeDetailsScreen.style.display = screen === 'details' ? 'block' : 'none';
        if (checkoutScreen) checkoutScreen.style.display = screen === 'checkout' ? 'block' : 'none';
        if (termsScreen) termsScreen.style.display = screen === 'terms' ? 'block' : 'none';
    }

    function closeUpgradeFlow() {
        if (upgradeFlow) upgradeFlow.style.display = 'none';
        mainSurface.forEach(element => {
            if (element) element.style.display = '';
        });
    }

    function selectPlan(plan) {
        selectedPlan = plan === 'ultimate' ? 'ultimate' : 'pro';
        const ultimate = selectedPlan === 'ultimate';
        [proPlanOption, ultimatePlanOption].forEach(option => {
            const selected = option?.dataset.plan === selectedPlan;
            option?.classList.toggle('selected', selected);
            option?.setAttribute('aria-pressed', String(selected));
            const action = option?.querySelector('.plan-action');
            if (action) action.textContent = selected ? 'Selected plan' : `Choose ${option.dataset.plan === 'ultimate' ? 'Ultimate' : 'Pro'}`;
        });
        if (checkoutPlanName) checkoutPlanName.textContent = ultimate ? 'Research Ultimate' : 'Research Pro';
        if (checkoutPlanPrice) checkoutPlanPrice.textContent = ultimate ? '$49 / month' : '$19 / month';
        if (checkoutSourceCapacity) checkoutSourceCapacity.textContent = ultimate ? 'More than 100' : 'Up to 100';
        if (checkoutDomainCapacity) checkoutDomainCapacity.textContent = ultimate ? 'Up to 3 domains' : '1 domain';
    }

    upgradeTile?.addEventListener('click', () => showUpgradeFlow('details'));
    upgradeTile?.addEventListener('keydown', event => {
        if (event.key === 'Enter' || event.key === ' ') showUpgradeFlow('details');
    });
    banner?.addEventListener('click', () => showUpgradeFlow('details'));
    banner?.addEventListener('keydown', event => {
        if (event.key === 'Enter' || event.key === ' ') showUpgradeFlow('details');
    });
    continueToCheckoutBtn?.addEventListener('click', () => showUpgradeFlow('checkout'));
    closeUpgradeBtn?.addEventListener('click', closeUpgradeFlow);
    backToUpgradeDetailsBtn?.addEventListener('click', () => showUpgradeFlow('details'));
    returnToResearchBtn?.addEventListener('click', closeUpgradeFlow);
    proPlanOption?.addEventListener('click', () => {
        selectPlan('pro');
        showUpgradeFlow('checkout');
    });
    ultimatePlanOption?.addEventListener('click', () => {
        selectPlan('ultimate');
        showUpgradeFlow('checkout');
    });
    termsLinkBtn?.addEventListener('click', () => showUpgradeFlow('terms'));
    backToCheckoutBtn?.addEventListener('click', () => showUpgradeFlow('checkout'));
    acceptTermsBtn?.addEventListener('click', () => {
        if (termsAgreement) termsAgreement.checked = true;
        showUpgradeFlow('checkout');
    });
    selectPlan('pro');

    async function refreshEntitlements() {
        const storage = await chrome.storage.local.get(["subscription_tier"]);
        isPaidUser = storage.subscription_tier === "paid" || isLocalTestingInstall;
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

    let currentRoutingSessionToken = "idle";
    const backgroundChannel = chrome.runtime.connect({ name: "nexus_popup_channel" });

    function sendBackgroundRequest(request) {
        return new Promise((resolve, reject) => {
            chrome.runtime.sendMessage(request, response => {
                if (chrome.runtime.lastError) {
                    reject(new Error(chrome.runtime.lastError.message));
                    return;
                }
                if (!response) {
                    reject(new Error('The background worker returned no response.'));
                    return;
                }
                handleBackgroundResponse(response);
                resolve(response);
            });
        });
    }

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
    paypalUpgradeBtn?.addEventListener('click', () => {
        if (!termsAgreement?.checked) {
            if (checkoutStatus) {
                checkoutStatus.className = 'error';
                checkoutStatus.innerText = 'Please review and accept the payment and refund terms first.';
                checkoutStatus.style.display = 'block';
            }
            return;
        }
        trackInterest('paypal_upgrade_clicks', 'PayPal checkout will open when payment integration is enabled.');
    });
    mpesaUpgradeBtn?.addEventListener('click', () =>
        trackInterest('mpesa_interest_clicks', 'M-PESA support is being evaluated. We recorded your interest.')
    );
    largeSourceInterestBtn?.addEventListener('click', () =>
        trackInterest('large_source_pack_clicks', 'We recorded your interest in larger source packs.')
    );
// extension/popup.js - Fragment 2 of 2 (Session Isolation & Event Triggers)
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
            return;
        }

        const data = response.data;
        if (data.status === 'error') {
            reportProcessingActive = false;
            if (statusDiv) {
                statusDiv.className = 'error';
                statusDiv.innerText = data.message || 'Processing failed.';
                statusDiv.style.display = 'block';
            }
            resetScribeButtonState();
            if (activeReportButton) activeReportButton.disabled = false;
            if (cancelScanBtn) cancelScanBtn.style.display = 'none';
            if (retryBtn && lastRequestContext?.action === 'trigger_nexus_scan') retryBtn.style.display = 'block';
            if (retryReportBtn && lastRequestContext?.action === 'trigger_docx_generation') retryReportBtn.style.display = 'block';
            currentRoutingSessionToken = "idle";
            return;
        }

        // Keep the report controls alive for any non-terminal host response.
        // Only a saved document or an explicit error should end report processing.
        if (reportProcessingActive &&
            data.action !== 'docx_generation_complete' &&
            !data.document_saved_at &&
            currentRoutingSessionToken === 'docx_generation_active') {
            return;
        }

        // --- PRODUCTION LOGIC VECTOR A: INTERCEPT CITATION DOCUMENT SCRIBE WRITES ---
        // By checking our request token, we block document passes from falling through into search logic
        if (currentRoutingSessionToken === "docx_generation_active" || data.action === "docx_generation_complete" || data.document_saved_at) {
            if (reportGenerationCancelled) return;
            reportProcessingActive = false;
            if (sProgressBar) sProgressBar.style.width = '100%';
            [sStep1, sStep2, sStep3, sStep4].forEach(s => markStep(s, 'success'));

            setTimeout(() => {
                resetScribeButtonState();
                if (activeReportButton) activeReportButton.disabled = false;
                currentRoutingSessionToken = "idle"; // Clear active session state
                if (sProgContainer) sProgContainer.style.display = 'none';
                if (draftStatus) {
                    // CRITICAL FIX: Extract the dynamic filename returned directly from your Python script execution run
                    const savedFile = data.document_saved_at ? data.document_saved_at : "comprehensive_pre_research_proposal_report.docx";

                    draftStatus.innerHTML = `✅ <strong>Project Writeup Compiled Successfully!</strong><br>👉 Word report file generated down to root storage path:<br><span style="color:#1e40af;font-size:11px;font-family:monospace;font-weight:700;word-break:break-all;">C:\\Users\\Abraham.Kemboi\\PycharmProjects\\Nexus-os\\${savedFile}</span>`;
                    draftStatus.style.display = 'block';
                }
                if (retryReportBtn) retryReportBtn.style.display = 'none';
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
    backgroundChannel.onMessage.addListener(handleBackgroundResponse);

    async function handleResearchSuccess(data, fromCache = false) {
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
        statusDiv.innerText = `${fromCache ? '♻️ Cached result loaded.' : '🎉 Scan complete.'} Audit database saved at ${data.excel_report_saved_at || 'the project folder'}.`;
        statusDiv.style.display = 'block';
                if (reportMetadata) {
                    reportMetadata.innerHTML = `
                        <strong>Research reports</strong><br>
                        Excel dossier: <span class="report-path">${data.discovery_report_name || 'Unavailable'}</span><br>
                        Directory: <span class="report-path">${data.discovery_report_directory || 'Unavailable'}</span>
                    `;
                    reportMetadata.style.display = 'block';
                }

                activeSessionIncludedPapers = data.included || [];
                activeSessionExcludedPapers = data.excluded || [];

                if (countInc) countInc.innerText = activeSessionIncludedPapers.length;
                if (countExc) countExc.innerText = activeSessionExcludedPapers.length;

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
        const cacheKey = JSON.stringify({
            topic: requestContext.topic,
            max_sources: requestContext.max_sources,
            domain: requestContext.domain,
            selected_inclusion_reasons: requestContext.selected_inclusion_reasons,
            uploads: requestContext.uploaded_sources.map(upload => `${upload.name}:${upload.data.length}`)
        });
        const cached = await chrome.storage.local.get(["research_cache_key", "research_cache_result"]);
        if (cached.research_cache_key === cacheKey && cached.research_cache_result) {
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
                if (fullDraftBtnText) fullDraftBtnText.innerText = 'Retrying full paper...';
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
            const storage = await chrome.storage.local.get(["subscription_tier"]);
            const isPaidUser = storage.subscription_tier === "paid" || isLocalTestingInstall;
            if (!isPaidUser) {
                if (draftStatus) {
                    draftStatus.innerText = "The Full Research Paper is available to paid users. Upgrade to unlock it.";
                    draftStatus.style.display = 'block';
                }
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
                uploaded_sources: await readUploads(),
                report_type: reportType,
                is_paid_user: isPaidUser
            };

            button.disabled = true;
            if (reportType === 'full_starter') {
                if (fullPaperSpinner) fullPaperSpinner.style.display = 'block';
            } else if (proposalSpinner) {
                proposalSpinner.style.display = 'block';
            }
            if (buttonTextId && document.getElementById(buttonTextId)) document.getElementById(buttonTextId).innerText = 'Compiling...';
            if (reportType === 'full_starter' && fullDraftBtnText) fullDraftBtnText.innerText = 'Generating full paper...';
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
            if (fullDraftBtnText) fullDraftBtnText.innerText = 'Generate Full Research Paper';
        }
        if (cancelReportBtn) cancelReportBtn.style.display = 'none';
    }
});
