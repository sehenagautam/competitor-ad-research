document.getElementById('capture').addEventListener('click', async () => {
    const status = document.getElementById('status');
    status.innerText = "Capturing...";

    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    
    if (!tab.url.includes("facebook.com/ads/library") && !tab.url.includes("tiktok.com")) {
        status.innerText = "Error: Not on an Ad Library page.";
        return;
    }

    chrome.tabs.sendMessage(tab.id, { action: "capture" }, (response) => {
        if (chrome.runtime.lastError) {
            status.innerText = "Error: Refresh the page and try again.";
            return;
        }
        
        if (response && response.ads) {
            status.innerText = `Found ${response.ads.length} ads! Sending to server...`;
            saveToServer(response.ads);
        } else {
            status.innerText = "No ads found on this page.";
        }
    });
});

async function saveToServer(ads) {
    const status = document.getElementById('status');
    try {
        const response = await fetch('http://localhost:8000/collect/extension', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ads: ads })
        });
        const result = await response.json();
        status.innerText = "Success! Ads saved to database.";
    } catch (error) {
        status.innerText = "Error: Could not connect to server.";
        console.error(error);
    }
}
