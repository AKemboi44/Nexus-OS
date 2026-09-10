console.log("[Nexus Background]: Long-lived Service Worker active.");

// Maintain an active pool tracking open extension popup window ports
let activePopupPort = null;

chrome.runtime.onConnect.addListener((popupPort) => {
    if (popupPort.name === "nexus_popup_channel") {
        activePopupPort = popupPort;
        console.log("[Nexus Background]: Long-lived UI Channel established safely.");

        activePopupPort.onMessage.addListener((request) => {
            if (request.action === "trigger_nexus_scan") {
                console.log("[Nexus Background]: Spawning Native messaging pipeline...");

                // Open the secure Windows Native Host Process thread loop handle connection
                const nativePort = chrome.runtime.connectNative("com.nexus.research.core");

                // Pack parameters natively and post directly down to python stdin
                const mcpPayload = {
                    method: "tools/call",
                    params: {
                        arguments: {
                            topic: request.topic,
                            custom_prompt: request.custom_prompt || null,
                            max_sources: parseInt(request.max_sources || 5),
                            domain: request.domain || "scholarly"
                        }
                    },
                    id: Date.now()
                };

                nativePort.postMessage(mcpPayload);

                // Seamlessly relay streaming frames up to the open popup overlay frame
                nativePort.onMessage.addListener((response) => {
                    console.log("[Nexus Background]: Inbound payload packet received from Python:", response);

                    if (activePopupPort) {
                        // Forward the raw packet object structure without splitting communication scopes
                        activePopupPort.postMessage({ success: true, data: response });
                    }

                    if (response.status === "success" || response.excel_report_saved_at) {
                        nativePort.disconnect();
                    }
                });

                nativePort.onDisconnect.addListener(() => {
                    const err = chrome.runtime.lastError;
                    if (err) {
                        console.warn("[Nexus Background Pipe Error]: Native line dropped:", err.message);
                        if (activePopupPort) {
                            activePopupPort.postMessage({ success: false, error: `Pipeline Severed: ${err.message}` });
                        }
                    }
                });
            }
        });

        popupPort.onDisconnect.addListener(() => {
            activePopupPort = null;
            console.log("[Nexus Background]: UI Panel overlay dropped by user view action.");
        });
    }
});
