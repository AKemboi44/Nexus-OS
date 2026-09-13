// extension/popup.js
console.log("[Nexus Popup] External script engine successfully compiled and mounted by Chrome V8!");

document.addEventListener('DOMContentLoaded', () => {
    const runButton = document.getElementById('runBtn');
    const btnSpinner = document.getElementById('btnSpinner');
    const btnText = document.getElementById('btnText');
    const statusDiv = document.getElementById('status');
    const previewSection = document.getElementById('previewSection');
    const summarySection = document.getElementById('summarySection');
    const auditTableBody = document.querySelector('#auditTable tbody');

    // Summary references
    const countInc = document.getElementById('countInc');
    const countExc = document.getElementById('countExc');

    // Progress UI references
    const progressContainer = document.getElementById('progressContainer');
    const progressBar = document.getElementById('progressBar');
    const step1 = document.getElementById('step1');
    const step2 = document.getElementById('step2');
    const step3 = document.getElementById('step3');
    const step4 = document.getElementById('step4');

    if (!runButton) return;

    const backgroundChannel = chrome.runtime.connect({ name: "nexus_popup_channel" });

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

    backgroundChannel.onMessage.addListener((response) => {
        if (!response || !response.success) {
            if (runButton) runButton.disabled = false;
            if (btnSpinner) btnSpinner.style.display = 'none';
            if (btnText) btnText.innerText = 'Launch Research Agents';
            if (progressContainer) progressContainer.style.display = 'none';

            // Mark trailing steps as failed on pipeline sever exceptions
            [step1, step2, step3, step4].forEach(s => {
                if (s && !s.classList.contains('completed')) markStep(s, 'fail');
            });

            if (statusDiv) {
                statusDiv.className = 'error';
                statusDiv.innerText = `Pipeline Connection Error:\n${response ? response.error : 'Connection dropped or engine error.'}`;
                statusDiv.style.display = 'block';
            }
            return;
        }

        const data = response.data;

        if (data.status === "processing") {
            // Processing frames mapped cleanly through the automated timeline engine below
        } else if (data.status === "success" || data.excel_report_saved_at) {
            if (progressBar) progressBar.style.width = '100%';
            [step1, step2, step3, step4].forEach(s => { if (s) markStep(s, 'success'); });

            setTimeout(() => {
                if (runButton) runButton.disabled = false;
                if (btnSpinner) btnSpinner.style.display = 'none';
                if (btnText) btnText.innerText = 'Launch Research Agents';
                if (progressContainer) progressContainer.style.display = 'none';

                if (statusDiv) {
                    statusDiv.className = 'success';
                    const executedDomain = data.domain_executed || "scholarly";
                    const fidelity = data.grounding_fidelity_score !== undefined ? data.grounding_fidelity_score : "N/A";
                    const relevance = data.topical_relevance_signal !== undefined ? data.topical_relevance_signal : "N/A";
                    const chunksIngested = data.pymupdf_fulltext_chunks_pushed !== undefined ? data.pymupdf_fulltext_chunks_pushed : 0;

                    // Rebranded string label update
                    statusDiv.innerText = `🎉 Scan Complete [${executedDomain.toUpperCase()}]!\n\n` +
                                         `Fidelity Score: ${fidelity}\n` +
                                         `Relevance Signal: ${relevance}\n` +
                                         `Evidence Ingested: ${chunksIngested} chunks\n\n` +
                                         `Research Audit spreadsheet index saved directly to your repository root workspace folder.`;
                    statusDiv.style.display = 'block';
                }

                if (auditTableBody) auditTableBody.innerHTML = "";

                const synthesisPayload = data.synthesis || {};
                const includedPapers = data.included || synthesisPayload.included || [];
                const excludedPapers = data.excluded || synthesisPayload.excluded || [];

                // Populate Summary Stat Numbers Dynamically
                if (countInc) countInc.innerText = includedPapers.length;
                if (countExc) countExc.innerText = excludedPapers.length;
                if (summarySection) summarySection.style.display = "block";
                if (previewSection) previewSection.style.display = "block";

                if (auditTableBody) {
                    if (Array.isArray(includedPapers) && includedPapers.length > 0) {
                        includedPapers.forEach(item => {
                            const row = document.createElement('tr');
                            row.innerHTML = `
                              <td><strong>${item.title || 'Untitled Work'}</strong><br><span style="color:#64748b;font-size:10px;">${item.venue || 'Repository'} (${item.year || 'n.d.'})</span></td>
                              <td><span class="badge badge-inc">PASSED</span></td>
                              <td>Cross-verified. Grounded validation count: ${item.citation_count || 0} upstream citations.</td>
                            `;
                            auditTableBody.appendChild(row);
                        });
                    } else {
                        const emptyRow = document.createElement('tr');
                        emptyRow.innerHTML = `<td colspan="3" style="text-align:center;color:#64748b;">No sources met the inclusion threshold criteria.</td>`;
                        auditTableBody.appendChild(emptyRow);
                    }

                    if (Array.isArray(excludedPapers) && excludedPapers.length > 0) {
                        excludedPapers.forEach(item => {
                            const row = document.createElement('tr');
                            row.innerHTML = `
                              <td>${item.title || 'Filtered Candidate Record'}<br><span style="color:#94a3b8;font-size:10px;">${item.provider_source || 'Discovery Endpoint'}</span></td>
                              <td><span class="badge badge-exc">SKIP</span></td>
                              <td style="color:#64748b;">${item.exclusion_reason || 'Duplicate footprint filter matched.'}</td>
                            `;
                            auditTableBody.appendChild(row);
                        });
                    }
                }
            }, 600);
        }
    });

    runButton.onclick = function(e) {
        e.preventDefault();
        const topic = document.getElementById('topic').value.trim();
        const domain = document.getElementById('domain').value;
        const max_sources = document.getElementById('max_sources').value;

        if (!topic) {
            if (statusDiv) {
                statusDiv.className = 'error';
                statusDiv.innerText = "Error: Target research topic field cannot be left blank.";
                statusDiv.style.display = 'block';
            }
            return;
        }

        runButton.disabled = true;
        if (btnSpinner) btnSpinner.style.display = 'block';
        if (btnText) btnText.innerText = 'Searching...';

        if (statusDiv) {
            statusDiv.style.display = 'none';
            statusDiv.className = '';
            statusDiv.innerText = '';
        }
        if (previewSection) previewSection.style.display = "none";
        if (summarySection) summarySection.style.display = "none";

        if (progressContainer) progressContainer.style.display = 'block';
        if (progressBar) progressBar.style.width = '10%';

        // Initialize Tracking States Cleanly
        markStep(step1, 'active');
        [step2, step3, step4].forEach(s => {
            if (s) {
                s.className = 'step-item';
                s.querySelector('.step-icon').innerText = '⚫';
            }
        });

        setTimeout(() => {
            if (runButton.disabled) {
                if (progressBar) progressBar.style.width = '35%';
                markStep(step1, 'success');
                markStep(step2, 'active');
            }
        }, 2000);

        setTimeout(() => {
            if (runButton.disabled) {
                if (progressBar) progressBar.style.width = '65%';
                markStep(step2, 'success');
                markStep(step3, 'active');
            }
        }, 5500);

        setTimeout(() => {
            if (runButton.disabled) {
                if (progressBar) progressBar.style.width = '85%';
                markStep(step3, 'success');
                markStep(step4, 'active');
            }
        }, 9000);

        backgroundChannel.postMessage({
            action: "trigger_nexus_scan",
            topic: topic,
            max_sources: max_sources,
            domain: domain
        });
    };
});
