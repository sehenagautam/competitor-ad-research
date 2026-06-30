from __future__ import annotations

import datetime
import hashlib
import json
import re
from typing import Iterable
from urllib.parse import urlparse

from backend.database import Ad, SessionLocal

DEFAULT_AD_REGION = "Nepal"
DEFAULT_ADVERTISER_LOCATION = "Nepal"


GENERIC_HEADLINES = {
    "meta ad",
    "meta scraped ad",
    "tiktok ad",
    "google ad",
    "google ad (no text)",
    "google ad (visual/no text)",
    "test headline",
}

NOISE_EXACT = {
    "see analytics",
    "ctr",
    "budget",
    "likes",
    "reach",
    "traffic",
    "conversions",
    "video views",
    "active",
    "inactive",
    "platforms",
    "sponsored",
    "eu transparency",
    "open dropdown",
    "see summary details",
    "see ad details",
    "this ad has multiple versions",
    "verified",
    "shop",
    "support",
    "hide_image",
    "close",
}

NOISE_PATTERNS = [
    re.compile(r"^top\s+\d+%$", re.IGNORECASE),
    re.compile(r"^\d+([.,]\d+)?[kmb]?$", re.IGNORECASE),
    re.compile(r"^\d+\s+likes?$", re.IGNORECASE),
    re.compile(r"^(low|medium|high)\s+budget$", re.IGNORECASE),
    re.compile(r"^library id[:\s]", re.IGNORECASE),
    re.compile(r"^started running on", re.IGNORECASE),
    re.compile(r"^ad details$", re.IGNORECASE),
    re.compile(r"^(video\w*\s+)?ad\s*\(\d+\s+(of|out of)\s+\d+\)$", re.IGNORECASE),
    re.compile(r"^(videocam\s+)?विज्ञापन\s*\(\d+\s+मध्ये\s+\d+\)$", re.IGNORECASE),
    re.compile(r"^\d+\s+ads?\s+use\s+this\s+creative\s+and\s+text$", re.IGNORECASE),
    re.compile(r"^[A-Za-z]{3}\s+\d{1,2},\s+\d{4}\s+-\s+[A-Za-z]{3}\s+\d{1,2},\s+\d{4}$", re.IGNORECASE),
    re.compile(r"^www\.[\w.-]+\.[a-z]{2,}$", re.IGNORECASE),
    re.compile(r"^[\w.-]+\.[a-z]{2,}/?$", re.IGNORECASE),
    re.compile(r"^rating.*\(\d+\)$", re.IGNORECASE),
    re.compile(r"^most items.*$", re.IGNORECASE),
]

META_STATUS_PATTERN = re.compile(r"^(Active|Inactive)$", re.IGNORECASE)
META_DATE_RANGE_PATTERN = re.compile(
    r"^(?P<start>[A-Za-z]{3}\s+\d{1,2},\s+\d{4})\s*-\s*(?P<end>[A-Za-z]{3}\s+\d{1,2},\s+\d{4})$"
)
DATE_LABEL_PATTERN = re.compile(r"^(?:Last shown date|Date last shown|अन्तिम पटक देखाइएको मिति)[:：]\s*(.+)$", re.IGNORECASE)
FORMAT_LABEL_PATTERN = re.compile(r"^(?:Format|ढाँचा)[:：]\s*(.+)$", re.IGNORECASE)
REGION_LABEL_PATTERN = re.compile(r"^(?:Shown in|संयुक्त राज्य अमेरिका मा देखाइएको|Displayed in)[:：]?\s*(.*)$", re.IGNORECASE)


def _clean_line(text: str | None) -> str:
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text).strip(" |-\n\t")
    return text.strip()


def _strip_summary_prefix(text: str) -> str:
    value = _clean_line(text)
    while True:
        updated = re.sub(r"^(Objective|Category|Likes|CTR ranking|Budget|Advertiser|Brand|Format|Region):\s*", "", value, flags=re.IGNORECASE)
        if updated == value:
            return value
        value = _clean_line(updated)


def _split_lines(raw_text: str | None) -> list[str]:
    if not raw_text:
        return []
    return [_clean_line(part) for part in re.split(r"[\n\r|]+", raw_text) if _clean_line(part)]


def _is_noise_line(line: str) -> bool:
    lowered = line.lower()
    if lowered in NOISE_EXACT:
        return True
    if lowered in GENERIC_HEADLINES:
        return True
    if len(line) < 3:
        return True
    if not any(char.isalpha() for char in line):
        return True
    return any(pattern.search(line) for pattern in NOISE_PATTERNS)


def _dedupe_preserve_order(lines: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for line in lines:
        key = line.casefold()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(line)
    return ordered


def _meaningful_lines(raw_text: str | None) -> list[str]:
    lines = _split_lines(raw_text)
    filtered = [line for line in lines if not _is_noise_line(line)]
    return _dedupe_preserve_order(filtered)


def _summarize_lines(lines: list[str], fallback: str, max_length: int = 220) -> tuple[str, str]:
    if not lines:
        return fallback, fallback

    headline_index = 0
    for index, line in enumerate(lines[:3]):
        if len(line.split()) >= 5 or len(line) >= 35:
            headline_index = index
            break

    headline = lines[headline_index][:120]
    ordered_lines = [lines[headline_index]] + [line for index, line in enumerate(lines) if index != headline_index]
    snippet_parts: list[str] = []

    for line in ordered_lines:
        candidate = " | ".join(snippet_parts + [line]) if snippet_parts else line
        if len(candidate) > max_length:
            break
        snippet_parts.append(line)

    snippet = " | ".join(snippet_parts) if snippet_parts else headline
    return headline, snippet


def _stable_external_id(platform: str, raw_text: str, prefix: str | None = None) -> str:
    digest = hashlib.sha1(f"{platform}:{raw_text}".encode("utf-8")).hexdigest()[:20]
    token = prefix or platform.lower()
    return f"{token}_{digest}"


def _parse_datetime(value) -> datetime.datetime | None:
    if not value:
        return None
    if isinstance(value, datetime.datetime):
        return value if value.tzinfo else value.replace(tzinfo=datetime.UTC)
    if isinstance(value, str):
        for parser in (
            lambda x: datetime.datetime.fromisoformat(x.replace("Z", "+00:00")),
            lambda x: datetime.datetime.strptime(x, "%b %d, %Y").replace(tzinfo=datetime.UTC),
            lambda x: datetime.datetime.strptime(x, "%Y-%m-%d").replace(tzinfo=datetime.UTC),
        ):
            try:
                return parser(value)
            except ValueError:
                continue
    return None


def _serialize_raw_payload(raw_data: dict) -> str:
    try:
        return json.dumps(raw_data, ensure_ascii=False, default=str)
    except TypeError:
        return json.dumps({"unserializable_payload": str(raw_data)}, ensure_ascii=False)


def _extract_domain(url: str | None) -> str | None:
    if not url:
        return None
    if "." not in url:
        return None
    target = url if "://" in url else f"https://{url}"
    try:
        return urlparse(target).netloc or None
    except ValueError:
        return None


def _default_record(platform: str, raw_payload: dict, query: str | None = None) -> dict:
    return {
        "platform": platform,
        "advertiser_name": None,
        "brand_name": None,
        "page_name": None,
        "content": None,
        "headline": None,
        "content_snippet": None,
        "status": None,
        "category": None,
        "objective": None,
        "ad_format": None,
        "platforms": None,
        "start_date": datetime.datetime.now(datetime.UTC),
        "end_date": None,
        "first_shown_date": None,
        "last_shown_date": None,
        "rank": None,
        "display_rank": None,
        "ctr_rank": None,
        "impression_count": None,
        "spend": None,
        "likes": None,
        "budget_level": None,
        "region": DEFAULT_AD_REGION,
        "advertiser_location": DEFAULT_ADVERTISER_LOCATION,
        "creative_url": None,
        "image_url": None,
        "landing_page": None,
        "landing_domain": None,
        "call_to_action": None,
        "variant_count": None,
        "raw_payload": _serialize_raw_payload(raw_payload),
        "query": query,
    }


def normalize_meta_ad(raw_ad: dict) -> dict:
    body = " ".join(raw_ad.get("ad_creative_bodies") or [])
    title = " ".join(raw_ad.get("ad_creative_link_titles") or [])
    description = " ".join(raw_ad.get("ad_creative_link_descriptions") or [])
    caption = " ".join(raw_ad.get("ad_creative_link_captions") or [])
    combined = "\n".join(part for part in [title, body, description, caption] if part)
    lines = _meaningful_lines(combined)
    headline, content = _summarize_lines(lines, "Meta ad copy unavailable")

    record = _default_record("Meta", raw_ad, query=raw_ad.get("query"))
    record.update(
        {
            "external_id": raw_ad.get("id") or _stable_external_id("Meta", combined or headline),
            "advertiser_name": raw_ad.get("page_name") or raw_ad.get("advertiser_name"),
            "brand_name": raw_ad.get("page_name") or raw_ad.get("advertiser_name"),
            "page_name": raw_ad.get("page_name"),
            "content": content,
            "headline": headline,
            "content_snippet": content,
            "status": raw_ad.get("status"),
            "category": raw_ad.get("category"),
            "objective": raw_ad.get("objective"),
            "ad_format": raw_ad.get("ad_format"),
            "platforms": ", ".join(raw_ad.get("publisher_platforms") or []) or None,
            "start_date": _parse_datetime(raw_ad.get("ad_delivery_start_time") or raw_ad.get("ad_creation_time")) or datetime.datetime.now(datetime.UTC),
            "end_date": _parse_datetime(raw_ad.get("ad_delivery_stop_time")),
            "creative_url": raw_ad.get("creative_url"),
            "landing_page": raw_ad.get("landing_page"),
            "landing_domain": _extract_domain(raw_ad.get("landing_page")),
            "spend": str(raw_ad.get("spend")) if raw_ad.get("spend") is not None else None,
            "impression_count": str(raw_ad.get("impressions")) if raw_ad.get("impressions") is not None else None,
            "region": raw_ad.get("region") or DEFAULT_AD_REGION,
            "advertiser_location": raw_ad.get("advertiser_location") or DEFAULT_ADVERTISER_LOCATION,
        }
    )
    return record


def normalize_meta_playwright_ad(raw_ad: dict) -> dict | None:
    raw_text = raw_ad.get("raw_text", "")
    lines = _meaningful_lines(raw_text)
    if not lines:
        return None

    headline, content = _summarize_lines(lines, "Meta ad copy unavailable")
    record = _default_record("Meta", raw_ad, query=raw_ad.get("query"))
    record.update(
        {
            "external_id": raw_ad.get("external_id") or _stable_external_id("Meta", raw_text or headline),
            "content": content,
            "headline": headline,
            "content_snippet": content,
            "creative_url": raw_ad.get("creative_url"),
            "image_url": raw_ad.get("image_url"),
            "landing_page": raw_ad.get("landing_page"),
            "landing_domain": _extract_domain(raw_ad.get("landing_page")),
            "platforms": ", ".join(raw_ad.get("platforms") or []) or None,
            "start_date": _parse_datetime(raw_ad.get("start_date")) or datetime.datetime.now(datetime.UTC),
            "end_date": _parse_datetime(raw_ad.get("end_date")),
            "status": raw_ad.get("status"),
            "region": raw_ad.get("region") or DEFAULT_AD_REGION,
            "advertiser_location": raw_ad.get("advertiser_location") or DEFAULT_ADVERTISER_LOCATION,
            "advertiser_name": raw_ad.get("advertiser_name"),
            "brand_name": raw_ad.get("advertiser_name"),
            "page_name": raw_ad.get("page_name") or raw_ad.get("advertiser_name"),
            "ad_format": raw_ad.get("ad_format"),
            "variant_count": raw_ad.get("variant_count"),
        }
    )

    for line in raw_ad.get("raw_lines") or []:
        if not record["status"] and META_STATUS_PATTERN.match(line):
            record["status"] = line
        if not record["page_name"] and line.lower() != "sponsored" and len(line) < 80:
            if raw_ad.get("advertiser_name") and line.casefold() == raw_ad.get("advertiser_name", "").casefold():
                record["page_name"] = line
        match = META_DATE_RANGE_PATTERN.match(line)
        if match:
            record["start_date"] = _parse_datetime(match.group("start")) or record["start_date"]
            record["end_date"] = _parse_datetime(match.group("end"))
        if "ads use this creative and text" in line.lower():
            record["variant_count"] = line.split(" ads ")[0]

    return record


def normalize_tiktok_ad(raw_data: dict) -> dict | None:
    raw_content = raw_data.get("raw_content") or []
    if isinstance(raw_content, list):
        cleaned_items = [_clean_line(str(item)) for item in raw_content if _clean_line(str(item))]
        raw_text = "\n".join(cleaned_items)
    else:
        cleaned_items = _split_lines(str(raw_content))
        raw_text = str(raw_content)

    prefixed_values: dict[str, str] = {}
    stripped_items: list[str] = []
    for item in cleaned_items:
        match = re.match(r"^(Objective|Category|Likes|CTR ranking|Budget|Advertiser|Brand|Format|Region):\s*(.+)$", item, re.IGNORECASE)
        if match:
            prefixed_values[match.group(1).lower()] = _strip_summary_prefix(match.group(2))
            stripped_items.append(_strip_summary_prefix(match.group(2)))
        else:
            stripped_items.append(_strip_summary_prefix(item))
    cleaned_items = stripped_items

    lines = _dedupe_preserve_order([item for item in cleaned_items if not _is_noise_line(item)])
    rich_lines = [line for line in lines if len(line.split()) >= 4 or len(line) >= 28]

    objective = prefixed_values.get("objective", raw_data.get("objective", ""))
    category = prefixed_values.get("category", raw_data.get("category", ""))
    ctr_rank = prefixed_values.get("ctr ranking", raw_data.get("ctr_rank", ""))
    budget = prefixed_values.get("budget", raw_data.get("budget_level", ""))
    likes = prefixed_values.get("likes", raw_data.get("likes", ""))
    advertiser = prefixed_values.get("advertiser", raw_data.get("advertiser_name", ""))

    if rich_lines:
        headline, content = _summarize_lines(rich_lines + [line for line in lines if line not in rich_lines], "TikTok creative details unavailable")
    else:
        known_objectives = {"reach", "traffic", "video views", "conversions", "lead generation", "app installs"}
        known_budgets = {"low", "medium", "high"}

        if not objective and len(cleaned_items) > 0 and cleaned_items[0].lower() in known_objectives:
            objective = cleaned_items[0]
        remaining_items = cleaned_items[1:] if objective else cleaned_items
        if not category:
            category = next((item for item in remaining_items if item.lower() not in known_budgets and not re.match(r"^Top\s+\d+%$", item, re.IGNORECASE) and not re.match(r"^\d+([.,]\d+)?[kmb]?$", item, re.IGNORECASE)), "")
        if not ctr_rank:
            ctr_rank = next((item for item in cleaned_items if re.match(r"^Top\s+\d+%$", item, re.IGNORECASE)), "")
        if not budget:
            budget = next((item for item in cleaned_items if item.lower() in known_budgets), "")
        if not likes:
            for index, item in enumerate(cleaned_items):
                if item.lower() == "likes" and index > 0:
                    likes = cleaned_items[index - 1]
                    break
        if category and objective.casefold() == category.casefold():
            objective = ""

        summary_parts = []
        if objective:
            summary_parts.append(f"Objective: {objective}")
        if category:
            summary_parts.append(f"Category: {category}")
        if likes:
            summary_parts.append(f"Likes: {likes}")
        if ctr_rank:
            summary_parts.append(f"CTR ranking: {ctr_rank}")
        if budget:
            summary_parts.append(f"Budget: {budget}")
        if advertiser:
            summary_parts.append(f"Advertiser: {advertiser}")

        headline = f"{category} top TikTok ad" if category else (f"{objective} TikTok ad" if objective else "")
        content = " | ".join(summary_parts) if summary_parts else headline

    if not headline or not content:
        return None

    record = _default_record("TikTok", raw_data, query=raw_data.get("query"))
    record.update(
        {
            "external_id": raw_data.get("external_id")
            or _stable_external_id(
                "TikTok",
                f"{raw_data.get('query', '')}|{raw_text or headline}",
                "tt",
            ),
            "advertiser_name": advertiser or raw_data.get("advertiser_name"),
            "brand_name": advertiser or raw_data.get("brand_name"),
            "page_name": advertiser or raw_data.get("page_name"),
            "content": content,
            "headline": headline,
            "content_snippet": content,
            "category": category or None,
            "objective": objective or None,
            "ad_format": raw_data.get("ad_format"),
            "start_date": _parse_datetime(raw_data.get("start_date")) or datetime.datetime.now(datetime.UTC),
            "rank": raw_data.get("rank"),
            "display_rank": raw_data.get("display_rank"),
            "ctr_rank": ctr_rank or None,
            "likes": likes or None,
            "budget_level": budget or None,
            "region": raw_data.get("region") or DEFAULT_AD_REGION,
            "advertiser_location": raw_data.get("advertiser_location") or DEFAULT_ADVERTISER_LOCATION,
            "creative_url": raw_data.get("creative_url"),
            "image_url": raw_data.get("image_url"),
            "landing_page": raw_data.get("landing_page"),
            "landing_domain": _extract_domain(raw_data.get("landing_page")),
            "call_to_action": raw_data.get("call_to_action"),
        }
    )
    return record


def normalize_google_ad(raw_data: dict) -> dict | None:
    raw_content = raw_data.get("raw_content") or []
    raw_lines = [_clean_line(str(item)) for item in raw_content if _clean_line(str(item))] if isinstance(raw_content, list) else _split_lines(str(raw_content))

    advertiser = _clean_line(raw_data.get("advertiser"))
    filtered_lines = []
    for line in raw_lines:
        lowered = line.casefold()
        if advertiser and lowered == advertiser.casefold():
            continue
        if lowered in {"sponsored", "verified", "report this ad"}:
            continue
        filtered_lines.append(line)

    lines = _dedupe_preserve_order([line for line in filtered_lines if not _is_noise_line(line)])
    if not lines:
        return None

    headline, content = _summarize_lines(lines, "Google ad creative captured without readable text")
    landing_page = next((line for line in raw_lines if _extract_domain(line)), raw_data.get("landing_page"))
    call_to_action = next((line for line in raw_lines if line.lower().startswith("shop ") or line.lower().startswith("browse")), None)
    last_shown_date = _parse_datetime(raw_data.get("last_shown_date"))

    record = _default_record("Google", raw_data, query=raw_data.get("query"))
    record.update(
        {
            "external_id": raw_data.get("external_id") or _stable_external_id("Google", "\n".join(raw_lines) or headline, "google"),
            "advertiser_name": advertiser or None,
            "brand_name": advertiser or None,
            "page_name": advertiser or None,
            "content": content,
            "headline": headline,
            "content_snippet": content,
            "ad_format": raw_data.get("ad_format"),
            "start_date": last_shown_date or datetime.datetime.now(datetime.UTC),
            "last_shown_date": last_shown_date,
            "display_rank": raw_data.get("display_rank") or raw_data.get("label"),
            "region": raw_data.get("region") or DEFAULT_AD_REGION,
            "advertiser_location": raw_data.get("advertiser_location") or DEFAULT_ADVERTISER_LOCATION,
            "creative_url": raw_data.get("creative_url"),
            "image_url": raw_data.get("image_url"),
            "landing_page": landing_page,
            "landing_domain": _extract_domain(landing_page),
            "call_to_action": call_to_action,
            "variant_count": raw_data.get("variant_count"),
        }
    )
    return record


def normalize_extension_ad(ad: dict, index: int = 0) -> dict | None:
    raw_text = ad.get("content", "")
    platform = ad.get("platform", "Unknown")
    lines = _meaningful_lines(raw_text)
    if not lines:
        return None
    headline, content = _summarize_lines(lines, f"{platform} ad capture unavailable")
    record = _default_record(platform, ad)
    record.update(
        {
            "external_id": _stable_external_id(platform, f"{index}:{raw_text}" or headline, "ext"),
            "content": content,
            "headline": headline,
            "content_snippet": content,
            "start_date": datetime.datetime.now(datetime.UTC),
        }
    )
    return record


def save_ad(ad_data: dict) -> None:
    db = SessionLocal()
    try:
        existing_ad = db.query(Ad).filter(Ad.external_id == ad_data["external_id"]).first()
        if existing_ad:
            for key, value in ad_data.items():
                if value is None and getattr(existing_ad, key, None) is not None:
                    continue
                if hasattr(existing_ad, key):
                    setattr(existing_ad, key, value)
            existing_ad.last_seen = datetime.datetime.now(datetime.UTC)
        else:
            db.add(Ad(**ad_data))
        db.commit()
    except Exception as exc:
        print(f"Error saving ad: {exc}")
        db.rollback()
    finally:
        db.close()
