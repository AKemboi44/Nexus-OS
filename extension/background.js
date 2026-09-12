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
                        let unpackedData = { status: "success" };

                        if (response && response.result) {
                            try {
                                const rawText = response.result;

                                // FIXED: Find the first '{' and last '}' to strip away human logs out of stdout
                                const firstBrace = rawText.indexOf('{');
                                const lastBrace = rawText.lastIndexOf('}');

                                if (firstBrace !== -1 && lastBrace !== -1 && lastBrace > firstBrace) {
                                    const cleanJsonString = rawText.substring(firstBrace, lastBrace + 1);
                                    const baseMcpResponse = JSON.parse(cleanJsonString);

                                    // Drill down through the MCP text response nesting block layer
                                    const textPayloadString = baseMcpResponse.result.content[0].text;
                                    const finalDataModel = JSON.parse(textPayloadString);

                                    unpackedData = finalDataModel;
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

                        // Send the clean, deeply-extracted dataset models straight up to popup.js
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
