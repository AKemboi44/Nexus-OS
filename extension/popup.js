console.log("[Nexus Popup] External script engine successfully compiled and mounted by Chrome V8!");

document.addEventListener('DOMContentLoaded', () => {
    const runButton = document.getElementById('runBtn');
    const statusDiv = document.getElementById('status');

    if (!runButton) return;

    // Listen for intermediate real-time progress text events sent from background.js
    chrome.runtime.onMessage.addListener((msg) => {
        if (msg.action === "update_loader_status") {
            statusDiv.className = 'loading';
            statusDiv.innerText = `⏳ Local Core Spawned!\n${msg.message}\n\nRunning active multi-agent review sweeps...`;
        }
    });

    runButton.onclick = async function(e) {
        e.preventDefault();
        const topic = document.getElementById('topic').value.trim();
        const custom_prompt = document.getElementById('custom_prompt').value.trim();
        const max_sources = document.getElementById('max_sources').value;

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

        chrome.runtime.sendMessage({
            action: "trigger_nexus_scan",
            topic: topic,
            custom_prompt: custom_prompt || null,
            max_sources: max_sources
        }, (response) => {
            if (!response || !response.success) {
                statusDiv.className = 'error';
                statusDiv.innerText = `Pipeline Connection Error:\n${response ? response.error : 'Connection lost.'}`;
                return;
            }

            const data = response.data;
            statusDiv.className = 'success';

            const fidelity = data.grounding_fidelity_score ?? "N/A";
            const relevance = data.topical_relevance_signal ?? "N/A";
            const reportPath = data.excel_report_saved_at ?? "Saved to workspace.";

            statusDiv.innerText = `🎉 Scan Complete!\n\nFidelity Score: ${fidelity}\nRelevance Signal: ${relevance}\n\nReport saved at:\n${reportPath}`;
        });
    };
});
