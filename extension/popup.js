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

    const step1 = document.getElementById('step1'); const step2 = document.getElementById('step2');
    const step3 = document.getElementById('step3'); const step4 = document.getElementById('step4');

    const postMvpReviewSection = document.getElementById('postMvpReviewSection');
    const synthesisFallbackCard = document.getElementById('synthesisFallbackCard');
    const draftDocBtn = document.getElementById('draftDocBtn');
    const scribeSpinner = document.getElementById('scribeSpinner');
    const draftBtnText = document.getElementById('draftBtnText');
    const draftStatus = document.getElementById('draftStatus');
    const sProgContainer = document.getElementById('scribeProgressContainer');
    const sProgressBar = document.getElementById('scribeProgressBar');
    const sStep1 = document.getElementById('sStep1'); const sStep2 = document.getElementById('sStep2');
    const sStep3 = document.getElementById('sStep3'); const sStep4 = document.getElementById('sStep4');

    const FREE_LIMIT = 5;

    let activeSessionIncludedPapers = [];

    let currentRoutingSessionToken = "idle";
    const backgroundChannel = chrome.runtime.connect({ name: "nexus_popup_channel" });

    function markStep(stepElement, state) {
        if (!stepElement) return; const iconSpan = stepElement.querySelector('.step-icon');
        if (state === 'active') { stepElement.className = 'step-item active'; if (iconSpan) iconSpan.innerText = '🔵'; }
        else if (state === 'success') { stepElement.className = 'step-item completed'; if (iconSpan) iconSpan.innerText = '✅'; }
        else if (state === 'fail') { stepElement.className = 'step-item failed'; if (iconSpan) iconSpan.innerText = '❌'; }
    }

    async function updateTierUI() {
        const data = await chrome.storage.local.get(["usage_count"]); const count = data.usage_count || 0;
        const remaining = Math.max(0, FREE_LIMIT - count);
        if (banner) banner.innerHTML = `<span>💎 <strong>Nexus Freemium Tier</strong> (${remaining}/${FREE_LIMIT} checks left)</span>`;
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
// extension/popup.js - Fragment 2 of 2 (Session Isolation & Event Triggers)
    backgroundChannel.onMessage.addListener(async (response) => {
        if (!response || !response.success || !response.data) {
            resetScribeButtonState();
            runButton.disabled = false;
            if (btnSpinner) btnSpinner.style.display = 'none';
            if (btnText) btnText.innerText = 'Launch Research Agents';
            if (progressContainer) progressContainer.style.display = 'none';
            currentRoutingSessionToken = "idle";
            if (statusDiv && response?.data?.message) {
                statusDiv.className = 'error';
                statusDiv.innerText = `Research failed: ${response.data.message}`;
                statusDiv.style.display = 'block';
            }
            return;
        }

        const data = response.data;

        // --- PRODUCTION LOGIC VECTOR A: INTERCEPT CITATION DOCUMENT SCRIBE WRITES ---
        // By checking our request token, we block document passes from falling through into search logic
        if (currentRoutingSessionToken === "docx_generation_active" || data.action === "docx_generation_complete" || data.document_saved_at) {
            if (sProgressBar) sProgressBar.style.width = '100%';
            [sStep1, sStep2, sStep3, sStep4].forEach(s => markStep(s, 'success'));

            setTimeout(() => {
                resetScribeButtonState();
                currentRoutingSessionToken = "idle"; // Clear active session state
                if (sProgContainer) sProgContainer.style.display = 'none';
                if (draftStatus) {
                    // CRITICAL FIX: Extract the dynamic filename returned directly from your Python script execution run
                    const savedFile = data.document_saved_at ? data.document_saved_at : "comprehensive_research_report_generation.docx";

                    draftStatus.innerHTML = `✅ <strong>Project Writeup Compiled Successfully!</strong><br>👉 Word report file generated down to root storage path:<br><span style="color:#1e40af;font-size:11px;font-family:monospace;font-weight:700;word-break:break-all;">C:\\Users\\Abraham.Kemboi\\PycharmProjects\\Nexus-os\\${savedFile}</span>`;
                    draftStatus.style.display = 'block';
                }
            }, 600);
            return;
        }


        // --- PRODUCTION LOGIC VECTOR B: INTERCEPT PRIMARY LITERATURE SWEEPS ---
        if (currentRoutingSessionToken === "research_scan_active" && data.status === "success") {
            if (progressBar) progressBar.style.width = '100%';
            [step1, step2, step3, step4].forEach(s => markStep(s, 'success'));

            const curr = await chrome.storage.local.get(["usage_count"]);
            await chrome.storage.local.set({ usage_count: (curr.usage_count || 0) + 1 });
            updateTierUI();

            setTimeout(() => {
                runButton.disabled = false;
                if (btnSpinner) btnSpinner.style.display = 'none';
                if (btnText) btnText.innerText = 'Launch Research Agents';
                if (progressContainer) progressContainer.style.display = 'none';

                statusDiv.className = 'success';
                statusDiv.innerText = `🎉 Scan Complete! Audit database saved at ${data.excel_report_saved_at || 'the project folder'}.`;
                statusDiv.style.display = 'block';

                auditTableBody.innerHTML = "";
                currentRoutingSessionToken = "idle"; // Clear session safely

                // Safely update references only if the search pass returns new ones
                if (data.included && data.included.length > 0) {
                    activeSessionIncludedPapers = data.included;
                }

                const countI = data.included ? data.included.length : 0;
                const countE = data.excluded ? data.excluded.length : 0;
                if (countInc) countInc.innerText = countI;
                if (countExc) countExc.innerText = countE;

                if (postMvpReviewSection) postMvpReviewSection.style.display = "block";
                if (synthesisFallbackCard) synthesisFallbackCard.style.display = "none";
                if (linkToSynthesisBtn) linkToSynthesisBtn.disabled = false;

                activeSessionIncludedPapers.forEach(item => {
                    const row = document.createElement('tr');
                    row.innerHTML = `<td><strong>${item.title || 'Untitled'}</strong></td><td><span class="badge badge-inc">PASSED</span></td><td>Verified. ${item.citation_count || 0} citations.</td>`;
                    auditTableBody.appendChild(row);
                });

                const exclusions = data.excluded || [];
                exclusions.forEach(item => {
                    const row = document.createElement('tr');
                    row.innerHTML = `<td>${item.title || 'Filtered'}</td><td><span class="badge badge-exc">SKIP</span></td><td>${item.exclusion_reason || 'Below precision baseline floor.'}</td>`;
                    auditTableBody.appendChild(row);
                });

                switchTab('dashboard');
            }, 600);
        }
    });

    runButton.onclick = async function(e) {
        e.preventDefault(); const topic = document.getElementById('topic').value.trim();
        if (!topic) return;

        currentRoutingSessionToken = "research_scan_active"; // Lock search session
        runButton.disabled = true; if (btnSpinner) btnSpinner.style.display = 'block';
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
            backgroundChannel.postMessage({
                action: "trigger_nexus_scan",
                topic: topic,
                max_sources: document.getElementById('max_sources').value,
                domain: document.getElementById('domain').value,
                uploaded_sources: await readUploads()
            });
        } catch (error) {
            runButton.disabled = false;
            if (statusDiv) {
                statusDiv.className = 'error';
                statusDiv.innerText = `Upload failed: ${error.message}`;
                statusDiv.style.display = 'block';
            }
        }
    };

    if (draftDocBtn) {
        draftDocBtn.onclick = async function(e) {
            e.preventDefault();

            // PROBLEM 2 RESOLVED: Guaranteed persistent reference dataset bounds.
            // This ensures clicking synthesis a second or third time will never stall the pipeline.
            currentRoutingSessionToken = "docx_generation_active";

            draftDocBtn.disabled = true;
            if (scribeSpinner) scribeSpinner.style.display = 'block';
            if (draftBtnText) draftBtnText.innerText = 'Compiling...';
            if (draftStatus) draftStatus.style.display = 'none';
            if (sProgContainer) sProgContainer.style.display = 'block';
            if (sProgressBar) sProgressBar.style.width = '10%';

            markStep(sStep1, 'active');
            [sStep2, sStep3, sStep4].forEach(s => { if(s){ s.className = 'step-item'; s.querySelector('.step-icon').innerText = '⚫'; } });

            setTimeout(() => { if (draftDocBtn.disabled) { if (sProgressBar) sProgressBar.style.width = '30%'; markStep(sStep1, 'success'); markStep(sStep2, 'active'); } }, 1200);
            setTimeout(() => { if (draftDocBtn.disabled) { if (sProgressBar) sProgressBar.style.width = '60%'; markStep(sStep2, 'success'); markStep(sStep3, 'active'); } }, 2800);
            setTimeout(() => { if (draftDocBtn.disabled) { if (sProgressBar) sProgressBar.style.width = '85%'; markStep(sStep3, 'success'); markStep(sStep4, 'active'); } }, 5000);

            backgroundChannel.postMessage({
                action: "trigger_docx_generation",
                topic: document.getElementById('topic').value.trim() || "ai token optimization techniques",
                included_sources: activeSessionIncludedPapers,
                uploaded_sources: await readUploads()
            });
        };
    }

    function resetScribeButtonState() {
        if (draftDocBtn) {
            draftDocBtn.disabled = false;
            if (scribeSpinner) scribeSpinner.style.display = 'none';
            if (draftBtnText) draftBtnText.innerText = 'Generate Cited Research Document';
        }
    }
});
