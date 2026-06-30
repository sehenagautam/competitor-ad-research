import asyncio
import sys
from collectors.meta_playwright import MetaPlaywrightCollector
from collectors.tiktok_collector import TikTokCollector
from collectors.google_collector import GoogleAdsCollector
from backend.utils import (
    normalize_google_ad,
    normalize_meta_playwright_ad,
    normalize_tiktok_ad,
    save_ad,
)

async def main():
    if len(sys.argv) < 3:
        print("Usage: python run_collector.py <platform> <query>")
        print("Platforms: meta, tiktok, google")
        return

    platform = sys.argv[1].lower()
    query = sys.argv[2]

    if platform == "meta":
        headless = "show" not in sys.argv
        collector = MetaPlaywrightCollector(headless=headless)
    elif platform == "tiktok":
        # Run in headful mode if 'show' is added to arguments
        headless = "show" not in sys.argv
        collector = TikTokCollector(headless=headless)
    elif platform == "google":
        headless = "show" not in sys.argv
        collector = GoogleAdsCollector(headless=headless)
    else:
        print(f"Unknown platform: {platform}")
        return

    print(f"Starting collection for '{query}' on {platform}...")
    results = await collector.collect(query)
    print(f"Found {len(results)} results.")
    
    for res in results:
        if platform == "tiktok":
            normalized = normalize_tiktok_ad(res)
        elif platform == "google":
            normalized = normalize_google_ad(res)
        else:
            normalized = normalize_meta_playwright_ad(res)

        if not normalized:
            print("Skipped low-value capture with no meaningful ad copy.")
            continue

        save_ad(normalized)
        print(f"Saved: {normalized['headline']}")

if __name__ == "__main__":
    asyncio.run(main())
