// extension/background.js - Side Panel Runtime Configuration
console.log("[Nexus Background Worker]: Active.");

// 1. Force the extension icon to open the secure native side panel context
chrome.sidePanel
  .setPanelBehavior({ openPanelOnActionClick: true })
  .catch((error) => console.error("Side panel assignment blocked:", error));

let activePopupPort = null;

chrome.runtime.onConnect.addListener((popupPort) => {
    if (popupPort.name === "nexus_popup_channel") {
        activePopupPort = popupPort;
        console.log("[Nexus Background]: Secure UI Channel established inside side panel.");

        activePopupPort.onMessage.addListener((request) => {
            if (request.action === "trigger_nexus_scan") {
                console.log("[Nexus Background]: Spawning Native messaging pipeline...");

                try {
                    // Connect cleanly down to your compiled standalone chrome_host.exe binary
                    const nativePort = chrome.runtime.connectNative("com.nexus.research.core");

                    nativePort.postMessage({
                        topic: request.topic,
                        max_sources: parseInt(request.max_sources || 5),
                        domain: request.domain || "scholarly"
                    });

                    nativePort.onMessage.addListener((response) => {
                        console.log("[Nexus Background]: Inbound parsed data from Python:", response);
                        if (activePopupPort) {
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
                } catch (nativeErr) {
                    console.error("Native Messaging execution error:", nativeErr);
                    if (activePopupPort) {
                        activePopupPort.postMessage({ success: false, error: `Native Setup Blocked: ${nativeErr.message}` });
                    }
                }
            }
        });

        popupPort.onDisconnect.addListener(() => {
            activePopupPort = null;
        });
    }
});
