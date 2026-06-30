from backend.database import Ad, SessionLocal
from backend.utils import (
    normalize_extension_ad,
    normalize_google_ad,
    normalize_meta_playwright_ad,
    normalize_tiktok_ad,
)


def main() -> None:
    db = SessionLocal()
    try:
        ads = db.query(Ad).order_by(Ad.id.asc()).all()
        seen: set[tuple[str, str, str]] = set()
        deleted = 0
        updated = 0

        for ad in ads:
            raw_payload = {"platform": ad.platform, "content": ad.content or ""}

            if ad.platform == "TikTok":
                normalized = normalize_tiktok_ad({"raw_content": [part.strip() for part in (ad.content or "").split("|") if part.strip()]})
            elif ad.platform == "Google":
                normalized = normalize_google_ad({"raw_content": [part.strip() for part in (ad.content or "").split("|") if part.strip()]})
            elif ad.platform == "Meta":
                normalized = normalize_meta_playwright_ad({"raw_text": "\n".join(part for part in [ad.headline, ad.content] if part)})
            else:
                normalized = normalize_extension_ad(raw_payload)

            if not normalized:
                db.delete(ad)
                deleted += 1
                continue

            dedupe_key = (
                normalized["platform"],
                normalized["headline"].casefold(),
                normalized["content"].casefold(),
            )
            if dedupe_key in seen:
                db.delete(ad)
                deleted += 1
                continue

            seen.add(dedupe_key)
            ad.headline = normalized["headline"]
            ad.content = normalized["content"]
            updated += 1

        db.commit()
        print(f"Updated {updated} ads and deleted {deleted} low-value or duplicate rows.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
