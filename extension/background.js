console.log("[Nexus Background]: Long-lived Service Worker active.");

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === "trigger_nexus_scan") {
        console.log("[Nexus Background]: Launching connection channel to Local Native Host Engine...");

        const port = chrome.runtime.connectNative("com.nexus.research.core");

        const mcpPayload = {
            method: "tools/call",
            params: {
                arguments: {
                    topic: request.topic,
                    custom_prompt: request.custom_prompt || null,
                    max_sources: parseInt(request.max_sources || 5)
                }
            },
            id: Date.now()
        };

        port.postMessage(mcpPayload);

        // Handle incoming data streams dynamically across multiple message frames
        port.onMessage.addListener((response) => {
            console.log("[Nexus Background]: Stream packet arrived from native host:", response);

            if (response.status === "processing") {
                // Forward the intermediate loader text status back to popup.js to show active tracking logs
                chrome.runtime.sendMessage({ action: "update_loader_status", message: response.message });
            } else if (response.status === "success" || response.excel_report_saved_at) {
                // Final data payload has arrived! Forward cleanly to popup UI and disconnect
                sendResponse({ success: true, data: response });
                port.disconnect();
            }
        });

        port.onDisconnect.addListener(() => {
            const err = chrome.runtime.lastError;
            if (err) {
                console.warn("[Nexus Background]: Native pipe disconnected:", err.message);
                sendResponse({ success: false, error: `Native Pipeline Crash: ${err.message}` });
            }
        });

        return true; // Keep response pipe open across long async calls
    }
});
