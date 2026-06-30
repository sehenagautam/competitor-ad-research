import asyncio
import re

from playwright.async_api import async_playwright

from .base import BaseCollector


class MetaPlaywrightCollector(BaseCollector):
    def __init__(self, headless=True, max_ads=30):
        self.base_url = "https://www.facebook.com/ads/library/"
        self.headless = headless
        self.max_ads = max_ads
        self.country_code = "NP"

    async def collect(self, query: str):
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            context = await browser.new_context(
                locale="en-NP",
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 900},
            )
            page = await context.new_page()

            url = f"{self.base_url}?active_status=all&ad_type=all&country={self.country_code}&q={query}&media_type=all"
            print(f"Navigating to {url}...")
            await page.goto(url, wait_until="networkidle")

            try:
                consent_btn = page.get_by_role("button", name=re.compile(r"Allow all cookies|Accept All", re.IGNORECASE))
                if await consent_btn.is_visible(timeout=5000):
                    await consent_btn.click()
            except Exception:
                pass

            print("Waiting for page content to stabilize...")
            try:
                await asyncio.sleep(5)
                await page.wait_for_selector("body", timeout=45000)
                for _ in range(3):
                    await page.mouse.wheel(0, 1200)
                    await asyncio.sleep(1.5)
            except Exception as exc:
                print(f"Meta Ads Library main content failed to appear: {exc}")
                await page.screenshot(path="meta_timeout_error.png")
                await browser.close()
                return []

            print("Extracting Meta ads...")
            results = await page.evaluate(
                """({ query, maxAds }) => {
                    const containers = Array.from(document.querySelectorAll('div[role="main"] div, div[data-pagelet] div, body div'))
                        .filter(node => {
                            const text = (node.innerText || '').trim();
                            return text.includes('Library ID') || text.includes('Started running on') || text.includes('See ad details');
                        });

                    const seen = new Set();
                    const records = [];

                    for (const node of containers) {
                        const text = (node.innerText || '').trim();
                        if (!text || text.length < 60) {
                            continue;
                        }

                        const lines = text.split(/\\n+/).map(line => line.trim()).filter(Boolean);
                        const libraryLine = lines.find(line => /Library ID/i.test(line)) || '';
                        const libraryId = (libraryLine.match(/Library ID[:\\s#]*([0-9]+)/i) || [null, null])[1];
                        const key = libraryId || lines.slice(0, 6).join('|').toLowerCase();
                        if (seen.has(key)) {
                            continue;
                        }
                        seen.add(key);

                        const advertiserLine = lines.find((line, idx) => lines[idx + 1]?.toLowerCase() === 'sponsored') || '';
                        const statusLine = lines.find(line => /^active$|^inactive$/i.test(line)) || '';
                        const dateRangeLine = lines.find(line => /^[A-Z][a-z]{2} \\d{1,2}, \\d{4}\\s*-\\s*[A-Z][a-z]{2} \\d{1,2}, \\d{4}$/.test(line)) || '';
                        const variantLine = lines.find(line => /ads use this creative and text|This ad has multiple versions/i.test(line)) || '';
                        const platformsLine = lines.find(line => /^Platforms$/i.test(line)) ? 'Platforms' : '';
                        const href = Array.from(node.querySelectorAll('a[href]')).map(a => a.href).find(Boolean) || null;
                        const img = node.querySelector('img')?.src || null;

                        records.push({
                            external_id: libraryId ? `meta_${libraryId}` : null,
                            raw_text: text,
                            raw_lines: lines,
                            advertiser_name: advertiserLine || null,
                            page_name: advertiserLine || null,
                            status: statusLine || null,
                            date_range_line: dateRangeLine || null,
                            variant_count: variantLine || null,
                            platforms: platformsLine ? ['Facebook', 'Instagram', 'Messenger', 'Audience Network'] : [],
                            creative_url: href,
                            image_url: img,
                            query,
                        });

                        if (records.length >= maxAds) {
                            break;
                        }
                    }

                    return records;
                }""",
                {"query": query, "maxAds": self.max_ads},
            )

            print(f"Found {len(results)} structured Meta ads.")
            await browser.close()
            return results

    def save(self, data):
        pass
