console.log("Ad Research Collector active");

function uniqueAds(items) {
    const seen = new Set();
    return items.filter(item => {
        const key = `${item.platform}:${item.content}`.toLowerCase();
        if (seen.has(key)) {
            return false;
        }
        seen.add(key);
        return true;
    });
}

function captureAds() {
    let ads = [];
    if (window.location.href.includes("facebook.com")) {
        // Meta Ad Library Card selectors
        const cards = document.querySelectorAll('div[class*="99p1"], div[class*="_7jws"]');
        cards.forEach(card => {
            if (card.innerText && card.innerText.length > 20) {
                ads.push({
                    content: card.innerText,
                    platform: "Meta"
                });
            }
        });
    } else if (window.location.href.includes("tiktok.com")) {
        // TikTok Card selectors
        const cards = document.querySelectorAll('div[class*="CardItem"]');
        cards.forEach(card => {
            if (card.innerText && card.innerText.length > 40) {
                ads.push({
                    content: card.innerText,
                    platform: "TikTok"
                });
            }
        });
    }
    return uniqueAds(ads);
}

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === "capture") {
        const ads = captureAds();
        sendResponse({ads: ads});
    }
});
