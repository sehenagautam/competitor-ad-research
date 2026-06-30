import asyncio
import re
from io import BytesIO

import numpy as np
import requests
from PIL import Image
from playwright.async_api import async_playwright
from rapidocr_onnxruntime import RapidOCR

from .base import BaseCollector


class GoogleAdsCollector(BaseCollector):
    def __init__(self, headless=True, max_ads=12):
        self.url = "https://adstransparency.google.com/?region=NP"
        self.headless = headless
        self.max_ads = max_ads
        self._ocr_engine = RapidOCR()

    async def collect(self, query: str):
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            context = await browser.new_context(
                locale="en-NP",
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 900},
            )
            page = await context.new_page()

            try:
                await self._open_search(page)
                await self._search_advertiser(page, query)
                cards = await self._extract_creative_cards(page)
                results = []

                for card in cards[: self.max_ads]:
                    detail = await self._extract_creative_detail(context, card["creative_url"])
                    record = self._build_result(card, detail, query)
                    if record:
                        results.append(record)

                print(f"Successfully extracted {len(results)} Google ads.")
                return results
            except Exception as exc:
                print(f"Google collection failed: {exc}")
                if not page.is_closed():
                    await page.screenshot(path="google_error.png")
                return []
            finally:
                await browser.close()

    async def _open_search(self, page):
        print(f"Navigating to {self.url}...")
        await page.goto(self.url, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(5000)

        try:
            consent_btn = page.get_by_role("button", name=re.compile(r"Accept all|Allow all", re.IGNORECASE))
            if await consent_btn.is_visible(timeout=3000):
                await consent_btn.click()
        except Exception:
            pass

    async def _search_advertiser(self, page, query: str):
        print(f"Searching for: {query}")

        search_input = page.locator("input[type='text'], input[type='search'], input").first
        await search_input.wait_for(timeout=10000)
        await search_input.click()
        await page.keyboard.press("Control+A")
        await page.keyboard.press("Backspace")
        await search_input.type(query, delay=120)
        await page.wait_for_timeout(3500)

        await page.wait_for_selector("[role='option']", timeout=15000)
        options = await page.locator("[role='option']").evaluate_all(
            """(elements) => elements.map((el, index) => {
                const lines = (el.innerText || "")
                    .split(/\\n+/)
                    .map(line => line.trim())
                    .filter(Boolean);
                const name = lines[0] || "";
                return {
                    index,
                    name,
                    text: lines.join(" | "),
                    nameLower: name.toLowerCase(),
                    textLower: lines.join(" | ").toLowerCase(),
                };
            })"""
        )

        option_index = self._choose_best_option(query, options)
        print(f"Choosing advertiser option: {options[option_index]['text']}")
        await page.locator("[role='option']").nth(option_index).click()
        await page.wait_for_timeout(6000)

        try:
            await page.wait_for_selector("creative-preview", timeout=30000)
        except Exception:
            await page.screenshot(path="google_ads_not_found.png")
            raise RuntimeError("No Google creative previews were loaded after advertiser selection.")

    def _choose_best_option(self, query: str, options: list[dict]) -> int:
        if not options:
            raise RuntimeError("Google advertiser search returned no options.")

        normalized_query = query.strip().casefold()

        def score(option: dict) -> tuple[int, int]:
            name = option["nameLower"].casefold()
            text = option["textLower"].casefold()
            exact = 3 if name == normalized_query else 0
            starts = 2 if name.startswith(normalized_query) else 0
            contains = 1 if normalized_query in text else 0
            return (exact + starts + contains, -option["index"])

        ranked = sorted(options, key=score, reverse=True)
        return ranked[0]["index"]

    async def _extract_creative_cards(self, page):
        await page.screenshot(path="google_final_ads.png")
        cards = await page.evaluate(
            """() => {
                const previews = Array.from(document.querySelectorAll("creative-preview"));
                const seen = new Set();

                return previews.map((preview, index) => {
                    const anchor = preview.querySelector("a[href*='/creative/']");
                    const image = preview.querySelector("img");
                    const advertiser = preview.querySelector(".advertiser-name")?.textContent?.trim() || "";
                    const href = anchor?.href || "";
                    const imageUrl = image?.src || "";
                    const creativeId = href.match(/\\/creative\\/([^?]+)/)?.[1] || "";
                    const key = creativeId || href || `${advertiser}-${index}`;

                    if (!href || seen.has(key)) {
                        return null;
                    }
                    seen.add(key);

                    return {
                        external_id: creativeId || null,
                        creative_url: href,
                        image_url: imageUrl,
                        advertiser,
                        label: anchor?.getAttribute("aria-label") || "",
                        display_rank: index + 1,
                    };
                }).filter(Boolean);
            }"""
        )

        print(f"Found {len(cards)} candidate Google creatives.")
        return cards

    async def _extract_creative_detail(self, context, creative_url: str):
        page = await context.new_page()
        try:
            await page.goto(creative_url, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(5000)
            detail = await page.evaluate(
                """() => {
                    const text = (document.body.innerText || '')
                        .split(/\\n+/)
                        .map(line => line.trim())
                        .filter(Boolean);
                    return {
                        lines: text,
                        title: document.title,
                    };
                }"""
            )
            return detail
        except Exception as exc:
            print(f"Google creative detail extraction failed for {creative_url}: {exc}")
            return {"lines": [], "title": None}
        finally:
            await page.close()

    def _build_result(self, card: dict, detail: dict, query: str):
        image_url = card.get("image_url")
        advertiser = card.get("advertiser", "").strip()
        creative_url = card.get("creative_url")
        external_id = card.get("external_id")

        if not image_url:
            print(f"Skipping Google creative without image source: {creative_url}")
            return None

        ocr_lines = self._ocr_image_lines(image_url)
        if not ocr_lines:
            print(f"Skipping Google creative with no OCR text: {creative_url}")
            return None

        detail_lines = detail.get("lines") or []
        return {
            "external_id": external_id,
            "platform": "Google",
            "raw_content": ocr_lines,
            "advertiser": advertiser,
            "creative_url": creative_url,
            "image_url": image_url,
            "label": card.get("label"),
            "display_rank": str(card.get("display_rank")),
            "ad_format": self._extract_labeled_value(detail_lines, ("Format", "ढाँचा")),
            "last_shown_date": self._extract_labeled_value(detail_lines, ("Last shown date", "अन्तिम पटक देखाइएको मिति")),
            "region": self._extract_region(detail_lines),
            "advertiser_location": self._extract_labeled_value(detail_lines, ("Shown in", "Displayed in")),
            "variant_count": next((line for line in detail_lines if "version" in line.lower() or "मध्ये" in line), None),
            "query": query,
        }

    def _extract_labeled_value(self, lines: list[str], labels: tuple[str, ...]) -> str | None:
        for line in lines:
            for label in labels:
                if line.lower().startswith(label.lower()):
                    parts = re.split(r"[:：]", line, maxsplit=1)
                    if len(parts) == 2:
                        return parts[1].strip()
        return None

    def _extract_region(self, lines: list[str]) -> str | None:
        for line in lines:
            lowered = line.lower()
            if "shown in" in lowered or "displayed in" in lowered or "मा देखाइएको" in lowered:
                return line
        return None

    def _ocr_image_lines(self, image_url: str) -> list[str]:
        response = requests.get(image_url, timeout=30)
        response.raise_for_status()

        image = Image.open(BytesIO(response.content)).convert("RGB")
        ocr_results, _ = self._ocr_engine(np.array(image))

        lines = []
        for item in ocr_results or []:
            text = item[1].strip()
            if text:
                lines.append(text)

        return self._dedupe_lines(lines)

    def _dedupe_lines(self, lines: list[str]) -> list[str]:
        seen = set()
        ordered = []
        for line in lines:
            cleaned = re.sub(r"\s+", " ", line).strip()
            if not cleaned:
                continue
            key = cleaned.casefold()
            if key in seen:
                continue
            seen.add(key)
            ordered.append(cleaned)
        return ordered

    def save(self, data):
        pass
