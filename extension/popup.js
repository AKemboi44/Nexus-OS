// extension/popup.js - Section 1: Initializers and Step State Machine
console.log("[Nexus Pro Core]: Mounted safely.");

document.addEventListener('DOMContentLoaded', () => {
    const runButton = document.getElementById('runBtn');
    const btnSpinner = document.getElementById('btnSpinner');
    const btnText = document.getElementById('btnText');
    const statusDiv = document.getElementById('status');
    const previewSection = document.getElementById('previewSection');
    const summarySection = document.getElementById('summarySection');
    const auditTableBody = document.querySelector('#auditTable tbody');
    const banner = document.getElementById('tierBanner');

    const countInc = document.getElementById('countInc');
    const countExc = document.getElementById('countExc');

    const progressContainer = document.getElementById('progressContainer');
    const progressBar = document.getElementById('progressBar');
    const step1 = document.getElementById('step1');
    const step2 = document.getElementById('step2');
    const step3 = document.getElementById('step3');
    const step4 = document.getElementById('step4');

    const FREE_LIMIT = 5;
    const backgroundChannel = chrome.runtime.connect({ name: "nexus_popup_channel" });

    // Step Toggler: Updates icons based on runtime status milestones
    function markStep(stepElement, state) {
        if (!stepElement) return;
        const iconSpan = stepElement.querySelector('.step-icon');
        if (state === 'active') {
            stepElement.className = 'step-item active';
            if (iconSpan) iconSpan.innerText = '🔵';
        } else if (state === 'success') {
            stepElement.className = 'step-item completed';
            if (iconSpan) iconSpan.innerText = '✅';
        } else if (state === 'fail') {
            stepElement.className = 'step-item failed';
            if (iconSpan) iconSpan.innerText = '❌';
        }
    }
    // extension/popup.js - Section 2: Token Management & Response Handling
    async function trackAnalyticsEvent(actionName, metadata = {}) {
        try {
            const storage = await chrome.storage.local.get(["nexus_user_id"]);
            let userId = storage.nexus_user_id;
            if (!userId) {
                userId = 'usr_' + Math.random().toString(36).substring(2, 15);
                await chrome.storage.local.set({ nexus_user_id: userId });
            }
            fetch("https://nexus-research-agents.com", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ user_id: userId, event: actionName, timestamp: new Date().toISOString(), context: metadata })
            }).catch(() => {});
        } catch (e) {}
    }

    async function updateTierUI() {
        const data = await chrome.storage.local.get(["usage_count", "premium_token"]);
        const count = data.usage_count || 0;
        const remaining = Math.max(0, FREE_LIMIT - count);
        if (banner) {
            banner.innerHTML = `<span>💎 <strong>Nexus Freemium Tier</strong> (${remaining}/${FREE_LIMIT} free agent checks left)</span>`;
        }
        return { isLimited: remaining <= 0, count };
    }

    updateTierUI();
    trackAnalyticsEvent("side_panel_opened");

    backgroundChannel.onMessage.addListener(async (response) => {
        if (!response || !response.success) {
            runButton.disabled = false;
            if (btnSpinner) btnSpinner.style.display = 'none';
            if (btnText) btnText.innerText = 'Launch Research Agents';
            if (progressContainer) progressContainer.style.display = 'none';
            [step1, step2, step3, step4].forEach(s => { if (s && !s.classList.contains('completed')) markStep(s, 'fail'); });
            if (statusDiv) {
                statusDiv.className = 'error';
                statusDiv.innerText = `Pipeline Connection Error:\n${response ? response.error : 'Connection dropped.'}`;
                statusDiv.style.display = 'block';
            }
            return;
        }

        const data = response.data;
        if (data.status === "success" || data.excel_report_saved_at) {
            if (progressBar) progressBar.style.width = '100%';
            [step1, step2, step3, step4].forEach(s => { if (s) markStep(s, 'success'); });

            const current = await chrome.storage.local.get(["usage_count"]);
            await chrome.storage.local.set({ usage_count: (current.usage_count || 0) + 1 });
            updateTierUI();

            setTimeout(() => {
                runButton.disabled = false;
                if (btnSpinner) btnSpinner.style.display = 'none';
                if (btnText) btnText.innerText = 'Launch Research Agents';
                if (progressContainer) progressContainer.style.display = 'none';

                statusDiv.className = 'success';
                const executedDomain = data.domain_executed || "scholarly";
                const reportLocationPath = data.excel_report_saved_at || "research_audit_report.xlsx";

                statusDiv.innerText = `🎉 Scan Complete [${executedDomain.toUpperCase()}]!\n\n` +
                                     `Fidelity Score: ${data.grounding_fidelity_score || 0}\n` +
                                     `Relevance Signal: ${data.topical_relevance_signal || 0}\n` +
                                     `Evidence Ingested: ${data.pymupdf_fulltext_chunks_pushed || 0} chunks\n\n` +
                                     `💾 Research Audit spreadsheet index saved directly to your repository root workspace folder:\n👉 ${reportLocationPath}`;
                statusDiv.style.display = 'block';

                auditTableBody.innerHTML = "";
                const includedPapers = data.included || [];
                const excludedPapers = data.excluded || [];

                if (countInc) countInc.innerText = includedPapers.length;
                if (countExc) countExc.innerText = excludedPapers.length;
                if (summarySection) summarySection.style.display = "block";
                if (previewSection) previewSection.style.display = "block";

                if (Array.isArray(includedPapers)) {
                    includedPapers.forEach(item => {
                        const row = document.createElement('tr');
                        row.innerHTML = `<td><strong>${item.title || 'Untitled'}</strong></td><td><span class="badge badge-inc">PASSED</span></td><td>Verified. ${item.citation_count || 0} citations.</td>`;
                        auditTableBody.appendChild(row);
                    });
                }
                if (Array.isArray(excludedPapers)) {
                    excludedPapers.forEach(item => {
                        const row = document.createElement('tr');
                        row.innerHTML = `<td>${item.title || 'Filtered'}</td><td><span class="badge badge-exc">SKIP</span></td><td>${item.exclusion_reason || 'Duplicate.'}</td>`;
                        auditTableBody.appendChild(row);
                    });
                }
            }, 600);
        }
    });
    // extension/popup.js - Section 3: Click Handlers and Dispatch Sequence
    runButton.onclick = async function(e) {
        e.preventDefault();

        const tierStatus = await updateTierUI();
        if (tierStatus.isLimited) {
            if (statusDiv) {
                statusDiv.className = 'error';
                statusDiv.innerText = "❌ Quota limit reached! Your 5 monthly free checks have run out.";
                statusDiv.style.display = 'block';
            }
            return;
        }

        const topic = document.getElementById('topic').value.trim();
        const domain = document.getElementById('domain').value;
        const max_sources = document.getElementById('max_sources').value;

        if (!topic) {
            if (statusDiv) {
                statusDiv.className = 'error';
                statusDiv.innerText = "Error: Target topic criteria input field cannot be left blank.";
                statusDiv.style.display = 'block';
            }
            return;
        }

        runButton.disabled = true;
        if (btnSpinner) btnSpinner.style.display = 'block';
        if (btnText) btnText.innerText = 'Searching...';

        if (statusDiv) statusDiv.style.display = 'none';
        if (previewSection) previewSection.style.display = "none";
        if (summarySection) summarySection.style.display = "none";
        if (progressContainer) progressContainer.style.display = 'block';
        if (progressBar) progressBar.style.width = '10%';

        markStep(step1, 'active');
        trackAnalyticsEvent("scan_started", { topic, domain, max_sources });

        setTimeout(() => { if (runButton.disabled) { if (progressBar) progressBar.style.width = '35%'; markStep(step1, 'success'); markStep(step2, 'active'); } }, 2000);
        setTimeout(() => { if (runButton.disabled) { if (progressBar) progressBar.style.width = '65%'; markStep(step2, 'success'); markStep(step3, 'active'); } }, 5500);
        setTimeout(() => { if (runButton.disabled) { if (progressBar) progressBar.style.width = '85%'; markStep(step3, 'success'); markStep(step4, 'active'); } }, 9000);

        backgroundChannel.postMessage({
            action: "trigger_nexus_scan",
            topic: topic,
            max_sources: max_sources,
            domain: domain
        });
    };
});
