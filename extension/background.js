console.log("[Nexus Background]: Long-lived Service Worker active.");

let activePopupPort = null;

chrome.runtime.onConnect.addListener((popupPort) => {
    if (popupPort.name === "nexus_popup_channel") {
        activePopupPort = popupPort;
        console.log("[Nexus Background]: Long-lived UI Channel established safely.");

        activePopupPort.onMessage.addListener((request) => {
            if (request.action === "trigger_nexus_scan") {
                console.log("[Nexus Background]: Spawning Native messaging pipeline...");

                const nativePort = chrome.runtime.connectNative("com.nexus.research.core");

                // Direct parameter mapping pass down the wire
                nativePort.postMessage({
                    topic: request.topic,
                    max_sources: parseInt(request.max_sources || 5),
                    domain: request.domain || "scholarly"
                });

                nativePort.onMessage.addListener((response) => {
                    console.log("[Nexus Background]: Clean parsed payload from Python:", response);

                    if (activePopupPort) {
                        // Forward the clean unboxed data model straight to popup.js
                        activePopupPort.postMessage({ success: true, data: response });
                    }
                    nativePort.disconnect();
                });

                nativePort.onDisconnect.addListener(() => {
                    const err = chrome.runtime.lastError;
                    if (err && activePopupPort) {
                        activePopupPort.postMessage({ success: false, error: `Pipeline Severed: ${err.message}` });
                    }
                });
            }
        });

        popupPort.onDisconnect.addListener(() => {
            activePopupPort = null;
        });
    }
});
