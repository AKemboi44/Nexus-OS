console.log("[Nexus Popup] External script engine successfully compiled and mounted by Chrome V8!");

document.addEventListener('DOMContentLoaded', () => {
    const runButton = document.getElementById('runBtn');
    const statusDiv = document.getElementById('status');

    if (!runButton) return;

    // 1. Initialize a long-lived data pipe channel directly up to the active background worker
    const backgroundChannel = chrome.runtime.connect({ name: "nexus_popup_channel" });

    // 2. Continuous Data Stream Listener: Intercepts all processing and success chunks over a single connection context
    backgroundChannel.onMessage.addListener((response) => {
        if (!response || !response.success) {
            statusDiv.className = 'error';
            statusDiv.innerText = `Pipeline Connection Error:\n${response ? response.error : 'Connection dropped or file lock error.'}`;
            return;
        }

        const data = response.data;

        // Dynamic State Router: Switches loading screens based on arriving status parameters
        if (data.status === "processing") {
            statusDiv.className = 'loading';
            statusDiv.innerText = `⏳ Local Core Spawned!\n${data.message}\n\nRunning active multi-agent review sweeps...`;
            statusDiv.style.display = 'block';
        } else if (data.status === "success" || data.excel_report_saved_at) {
            statusDiv.className = 'success';

            // Safe defensive fallbacks to map missing structural payload parameters cleanly
            const executedDomain = data.domain_executed || "scholarly";
            const fidelity = data.grounding_fidelity_score !== undefined ? data.grounding_fidelity_score : "N/A";
            const relevance = data.topical_relevance_signal !== undefined ? data.topical_relevance_signal : "N/A";
            const reportPath = data.excel_report_saved_at || "Saved to workspace.";
            const chunksIngested = data.pymupdf_fulltext_chunks_pushed !== undefined ? data.pymupdf_fulltext_chunks_pushed : 0;
            const apaCitation = data.apa_format_citation || "N/A";
            const bluebookCitation = data.bluebook_format_citation || "N/A";

            // Unfurl entire multi-agent analytic array framework right to your user overlay window view
            statusDiv.innerText = `🎉 Scan Complete [${executedDomain.toUpperCase()}]!\n\n` +
                                 `Fidelity Score: ${fidelity}\n` +
                                 `Relevance Signal: ${relevance}\n` +
                                 `PyMuPDF Ingested: ${chunksIngested} Full-text blocks\n\n` +
                                 `Report saved at:\n${reportPath}\n\n` +
                                 `APA Citation:\n${apaCitation}\n\n` +
                                 `Bluebook Citation:\n${bluebookCitation}`;
            statusDiv.style.display = 'block';
        }
    });

    runButton.onclick = async function(e) {
        e.preventDefault();
        const topic = document.getElementById('topic').value.trim();
        const custom_prompt = document.getElementById('custom_prompt').value.trim();
        const max_sources = document.getElementById('max_sources').value;
        const domain = document.getElementById('domain').value;

        statusDiv.style.display = 'none';
        statusDiv.className = '';
        statusDiv.innerText = '';

        if (!topic) {
            statusDiv.className = 'error';
            statusDiv.innerText = "Error: Target research topic field cannot be left blank.";
            statusDiv.style.display = 'block';
            return;
        }

        statusDiv.className = 'loading';
        statusDiv.innerText = "Spawning local multi-agent research core...\nConnecting Native Windows stdio channels...";
        statusDiv.style.display = 'block';

        // Post your configuration instruction down the open stream data channel handle link
        backgroundChannel.postMessage({
            action: "trigger_nexus_scan",
            topic: topic,
            custom_prompt: custom_prompt || null,
            max_sources: max_sources,
            domain: domain
        });
    };
});
