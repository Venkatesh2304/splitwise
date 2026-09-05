// Configurable Base Server URL
const DEFAULT_SERVER_URL = "http://127.0.0.1:5002"; // Change to http://13.235.142.203:5002 for AWS EC2

document.addEventListener("DOMContentLoaded", () => {
    const serverUrlInput = document.getElementById("serverUrl");
    const syncBtn = document.getElementById("syncBtn");
    const statusDiv = document.getElementById("status");

    // Load saved server URL preference
    chrome.storage.local.get(["serverUrl"], (res) => {
        if (res.serverUrl) {
            serverUrlInput.value = res.serverUrl;
        } else {
            serverUrlInput.value = DEFAULT_SERVER_URL;
        }
    });

    serverUrlInput.addEventListener("change", () => {
        let val = serverUrlInput.value.trim().replace(/\/$/, "");
        chrome.storage.local.set({ serverUrl: val });
    });

    function showStatus(text, type = "info") {
        statusDiv.className = `status-${type}`;
        statusDiv.style.display = "block";
        statusDiv.textContent = text;
    }

    syncBtn.addEventListener("click", async () => {
        const serverUrl = serverUrlInput.value.trim().replace(/\/$/, "");
        syncBtn.disabled = true;
        showStatus("📡 Connecting to active tab on blinkit.com...", "info");

        try {
            // Find active tab
            const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
            if (!tab || !tab.url || !tab.url.includes("blinkit.com")) {
                showStatus("❌ Please open and log into https://blinkit.com first!", "error");
                syncBtn.disabled = false;
                return;
            }

            // Execute raw order extraction inside active tab
            showStatus("🔍 Extracting session tokens & raw order history...", "info");
            const [results] = await chrome.scripting.executeScript({
                target: { tabId: tab.id },
                func: extractBlinkitRawBundle
            });

            const bundle = results ? results.result : null;

            if (!bundle || bundle.error) {
                showStatus(`❌ ${bundle?.error || "Failed to extract session from blinkit.com"}`, "error");
                syncBtn.disabled = false;
                return;
            }

            showStatus(`📦 Extracted ${Object.keys(bundle.details_by_order_id || {}).length} orders for +91-${bundle.phone_number}.\n🚀 Syncing to server: ${serverUrl}...`, "info");

            // Post to backend server (Extension background/popup fetch bypasses page mixed content)
            const endpoint = `${serverUrl}/api/blinkit/sync_manual/`;
            const resp = await fetch(endpoint, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    phone_number: bundle.phone_number,
                    json_data: bundle
                })
            });

            if (!resp.ok) {
                throw new Error(`Server returned HTTP ${resp.status}: ${resp.statusText}`);
            }

            const data = await resp.json();
            showStatus(`🎉 SUCCESS!\n${data.message || 'Orders synced successfully!'}\nSynced items: ${data.count || 0}`, "success");
        } catch (err) {
            showStatus(`🚨 Sync failed: ${err.message}`, "error");
        } finally {
            syncBtn.disabled = false;
        }
    });
});

// Function injected and executed inside the blinkit.com browser tab
async function extractBlinkitRawBundle() {
    let accessToken = null;
    let phoneNumber = null;

    try {
        const authObj = JSON.parse(localStorage.getItem("auth") || "{}");
        accessToken = authObj.accessToken;
        phoneNumber = authObj.phoneNumber;
    } catch(e) {}

    if (!accessToken) {
        const match = document.cookie.match(/gr_1_accessToken=([^;]+)/);
        if (match) accessToken = decodeURIComponent(match[1]);
    }

    if (!phoneNumber) {
        try {
            const userObj = JSON.parse(localStorage.getItem("user") || "{}");
            phoneNumber = userObj.phone;
        } catch(e) {}
    }

    let authKey = localStorage.getItem("authKey");

    if (!accessToken || !authKey) {
        return { error: "Tokens missing! Please make sure you are logged into blinkit.com" };
    }

    if (!phoneNumber) {
        return { error: "Phone number could not be detected in localStorage" };
    }

    const headers = {
        "Content-Type": "application/json",
        "app_client": "consumer_web",
        "access_token": accessToken,
        "auth_key": authKey
    };

    // 1. Order History
    const historyRes = await fetch("https://blinkit.com/v1/layout/order_history", {
        method: "POST",
        headers: headers,
        body: JSON.stringify({})
    });

    if (!historyRes.ok) {
        return { error: `Order history API failed with HTTP ${historyRes.status}` };
    }

    const orderHistoryRaw = await historyRes.json();

    const rawText = JSON.stringify(orderHistoryRaw);
    const orderMatches = [...rawText.matchAll(/"order_id":\s*"?(\d+)"?/g)];
    const cartMatches = [...rawText.matchAll(/cart_id=(\d+)/g)];

    const orderIds = [...new Set(orderMatches.map(m => m[1]))];

    // 2. Details for each order
    const detailsByOrderId = {};
    for (let i = 0; i < orderIds.length; i++) {
        const orderId = orderIds[i];
        const cartId = cartMatches[i] ? cartMatches[i][1] : null;

        let url = `https://blinkit.com/v1/layout/order_details_v2?order_id=${orderId}`;
        if (cartId) url += `&cart_id=${cartId}`;

        try {
            const dtRes = await fetch(url, {
                method: "POST",
                headers: headers,
                body: JSON.stringify({})
            });
            if (dtRes.ok) {
                detailsByOrderId[orderId] = await dtRes.json();
            }
        } catch (e) {}
    }

    return {
        phone_number: phoneNumber,
        order_history: orderHistoryRaw,
        details_by_order_id: detailsByOrderId
    };
}
