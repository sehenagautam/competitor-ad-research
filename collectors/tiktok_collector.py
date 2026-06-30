import asyncio
import re

from playwright.async_api import async_playwright

from .base import BaseCollector


class TikTokCollector(BaseCollector):
    def __init__(self, headless=True, max_ads=40):
        self.url = "https://ads.tiktok.com/business/creativecenter/inspiration/topads/pc/en"
        self.headless = headless
        self.max_ads = max_ads

    async def collect(self, query: str = ""):
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            context = await browser.new_context(
                locale="en-NP",
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
                viewport={"width": 1440, "height": 900},
            )
            page = await context.new_page()

            print(f"Navigating to {self.url}...")
            await page.goto(self.url, wait_until="networkidle")

            try:
                print("Waiting for TikTok ad cards...")
                await page.wait_for_selector('[class*="Card"]', timeout=30000)
            except Exception:
                print(f"Selector timeout. Current Page Title: {await page.title()}")
                await page.screenshot(path="tiktok_error.png")
                await browser.close()
                return []

            results = await page.evaluate(
                """({ query, maxAds }) => {
                    const selectors = [
                        'div[class*="CardItem"]',
                        'div[class*="TopadsCard"]',
                        'div[class*="Card"]'
                    ];
                    const cards = selectors.flatMap(selector => Array.from(document.querySelectorAll(selector)));
                    const seen = new Set();
                    const blocked = ['see analytics'];
                    const out = [];

                    const takeMetric = (lines, pattern) => lines.find(line => pattern.test(line)) || null;

                    for (const card of cards) {
                        const text = (card.innerText || '').trim();
                        if (!text || text.length < 40) {
                            continue;
                        }

                        const lines = text
                            .split(/\\n+/)
                            .map(line => line.trim())
                            .filter(Boolean)
                            .filter(line => !blocked.includes(line.toLowerCase()));

                        if (lines.length < 2) {
                            continue;
                        }

                        const key = lines.join('|').toLowerCase();
                        if (seen.has(key)) {
                            continue;
                        }
                        seen.add(key);

                        const objective = lines.find(line => /reach|traffic|video views|conversions|lead generation|app installs/i.test(line)) || null;
                        const category = lines.find(line => /beauty|skincare|cosmetics|food|beverages|machinery|games|culture|art|real estate|fashion|electronics/i.test(line)) || null;
                        const ctrRank = takeMetric(lines, /^Top\\s+\\d+%$/i);
                        const budget = takeMetric(lines, /^(Low|Medium|High)$/i);
                        const likesIndex = lines.findIndex(line => /^Likes$/i.test(line));
                        const likes = likesIndex > 0 ? lines[likesIndex - 1] : null;
                        const cta = lines.find(line => /^Shop now|Learn more|Sign up|Download$/i.test(line)) || null;
                        const rank = lines.find(line => /^#\\d+$/i.test(line)) || null;
                        const advertiser = lines.find(line => /official|store|shop|brand/i.test(line) && line.length < 60) || null;
                        const links = Array.from(card.querySelectorAll('a[href]')).map(a => a.href).filter(Boolean);
                        const imageUrl = card.querySelector('img')?.src || null;

                        out.push({
                            external_id: null,
                            raw_content: lines.slice(0, 20),
                            platform: 'TikTok',
                            objective,
                            category,
                            ctr_rank: ctrRank,
                            budget_level: budget,
                            likes,
                            call_to_action: cta,
                            rank,
                            advertiser_name: advertiser,
                            creative_url: links[0] || null,
                            landing_page: links.find(link => !link.includes('tiktok.com')) || null,
                            image_url: imageUrl,
                            query,
                        });

                        if (out.length >= maxAds) {
                            break;
                        }
                    }

                    return out;
                }""",
                {"query": query, "maxAds": self.max_ads},
            )

            filtered_results = self._filter_query_specific_results(results, query)
            print(
                f"Found {len(results)} TikTok cards after deduplication and filtering, "
                f"kept {len(filtered_results)} query-specific cards for '{query}'."
            )
            await asyncio.sleep(1)
            await browser.close()
            return filtered_results

    def save(self, data):
        pass

    def _filter_query_specific_results(self, results: list[dict], query: str) -> list[dict]:
        query_tokens = self._query_tokens(query)
        if not query_tokens:
            return results

        kept: list[dict] = []
        for item in results:
            haystack_parts = []
            raw_content = item.get("raw_content") or []
            if isinstance(raw_content, list):
                haystack_parts.extend(str(part) for part in raw_content)
            else:
                haystack_parts.append(str(raw_content))
            for key in ("advertiser_name", "creative_url", "landing_page", "category", "objective"):
                if item.get(key):
                    haystack_parts.append(str(item[key]))
            haystack = " ".join(haystack_parts).casefold()
            if self._matches_query_tokens(haystack, query_tokens):
                kept.append(item)
        return kept

    def _query_tokens(self, query: str) -> list[str]:
        words = [word.casefold() for word in re.findall(r"[a-zA-Z0-9]+", query)]
        stop_words = {"for", "and", "the", "with", "from", "this", "that", "ads", "ad"}
        tokens: list[str] = []
        for word in words:
            if word in stop_words:
                continue
            if len(word) >= 4:
                tokens.append(word)
            elif len(words) == 1 and len(word) >= 3:
                tokens.append(word)

        expanded: list[str] = []
        for token in tokens:
            expanded.append(token)
            if token.endswith("s") and len(token) > 4:
                expanded.append(token[:-1])
            elif len(token) > 4:
                expanded.append(f"{token}s")
        seen = set()
        ordered = []
        for token in expanded:
            if token in seen:
                continue
            seen.add(token)
            ordered.append(token)
        return ordered

    def _matches_query_tokens(self, haystack: str, query_tokens: list[str]) -> bool:
        if not haystack:
            return False
        matches = sum(1 for token in query_tokens if token in haystack)
        if len(query_tokens) == 1:
            return matches >= 1
        return matches >= max(1, min(2, len(query_tokens)))
