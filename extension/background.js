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

                nativePort.onMessage.addListener((response) => {
                    console.log("[Nexus Background]: Inbound payload packet received from Python:", response);

                    if (activePopupPort) {
                        let unpackedData = {};

                        if (response && response.result) {
                            try {
                                const rawText = response.result;
                                const firstBrace = rawText.indexOf('{');
                                const lastBrace = rawText.lastIndexOf('}');

                                if (firstBrace !== -1 && lastBrace !== -1 && lastBrace > firstBrace) {
                                    const cleanJsonString = rawText.substring(firstBrace, lastBrace + 1);
                                    let parsedPayload = JSON.parse(cleanJsonString);

                                    // Layer 1: Drill through standard JSON-RPC envelope structures explicitly via index [0]
                                    if (parsedPayload.result && parsedPayload.result.content) {
                                        const contentArray = parsedPayload.result.content;
                                        if (Array.isArray(contentArray) && contentArray[0] && contentArray[0].text) {
                                            parsedPayload = JSON.parse(contentArray[0].text);
                                        } else if (contentArray.text) {
                                            parsedPayload = JSON.parse(contentArray.text);
                                        }
                                    }

                                    // Layer 2: Ensure any outer string serialization layer is unrolled
                                    if (typeof parsedPayload === 'string') {
                                        parsedPayload = JSON.parse(parsedPayload);
                                    }

                                    unpackedData = parsedPayload;
                                } else {
                                    unpackedData.message = rawText;
                                }
                            } catch (e) {
                                console.warn("[Nexus Background Parsing Exception]:", e);
                                unpackedData.message = response.result;
                            }
                        } else if (response) {
                            unpackedData = response;
                        }

                        // Force standard success flags so popup.js triggers the dynamic display route
                        if (!unpackedData.status) {
                            unpackedData.status = "success";
                        }

                        console.log("[Nexus Background]: Forwarding fully unrolled data back to popup:", unpackedData);
                        activePopupPort.postMessage({ success: true, data: unpackedData });
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
