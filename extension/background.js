// extension/background.js - Stateless Single-Flight Request Router
function dispatchNativeRequest(messageFromUI, respond) {
    let responded = false;
    const reply = payload => {
        if (responded) return;
        responded = true;
        respond(payload);
    };
    try {
        console.log("[Nexus Background]: Dispatched transaction request container:", messageFromUI.action);

        // Leverage sendNativeMessage to open a bulletproof one-shot transaction channel
        chrome.runtime.sendNativeMessage(
            "com.nexus.research.core",
            messageFromUI,
            (responseFromPython) => {
                // Check if the runtime context encountered a binary routing error
                if (chrome.runtime.lastError) {
                    console.error("[Nexus Background Error]: Native execution failed:", chrome.runtime.lastError.message);
                    reply({
                        success: false,
                        error: chrome.runtime.lastError.message
                    });
                    return;
                }

                if (responseFromPython) {
                    console.log("[Nexus Background]: Payload fully received from server:", responseFromPython);
                    // Pass the complete dataset back to update the front-end popup UI
                    reply({ success: true, data: responseFromPython });
                } else {
                    console.warn("[Nexus Background Warning]: Received empty response packet from host executable.");
                    reply({ success: false, error: "Host provided an empty payload." });
                }
            }
        );
    } catch (error) {
        console.error("[Nexus Background Error]: Native request could not start:", error);
        reply({
            success: false,
            error: `Native request could not start: ${error.message}`
        });
    }
}

chrome.runtime.onMessage.addListener((messageFromUI, sender, sendResponse) => {
    dispatchNativeRequest(messageFromUI, sendResponse);
    return true;
});

chrome.runtime.onConnect.addListener((popupPort) => {
    if (popupPort.name !== "nexus_popup_channel") return;
    console.log("[Nexus Background]: Connected to popup window framework.");
    popupPort.onMessage.addListener((messageFromUI) => {
        dispatchNativeRequest(messageFromUI, response => {
            try {
                popupPort.postMessage(response);
            } catch (error) {
                console.warn("[Nexus Background]: Popup port disconnected before response delivery.", error);
            }
        });
    });
});
