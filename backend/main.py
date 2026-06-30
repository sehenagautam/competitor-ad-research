import os
from typing import Iterable, List, Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import func, or_

from backend.database import Ad, SessionLocal, init_db
from backend.reporting import generate_product_pdf
from backend.utils import (
    normalize_extension_ad,
    normalize_google_ad,
    normalize_meta_ad,
    normalize_meta_playwright_ad,
    normalize_tiktok_ad,
    save_ad,
)
from collectors.google_collector import GoogleAdsCollector
from collectors.meta_api import MetaAPICollector
from collectors.meta_playwright import MetaPlaywrightCollector
from collectors.tiktok_collector import TikTokCollector


app = FastAPI(title="Competitor Ad Research API")


@app.on_event("startup")
def startup():
    init_db()


def serialize_ad(ad: Ad) -> dict:
    return {
        "id": ad.id,
        "platform": ad.platform,
        "headline": ad.headline,
        "content": ad.content,
        "content_snippet": ad.content_snippet,
        "advertiser_name": ad.advertiser_name,
        "brand_name": ad.brand_name,
        "page_name": ad.page_name,
        "status": ad.status,
        "category": ad.category,
        "objective": ad.objective,
        "ad_format": ad.ad_format,
        "platforms": ad.platforms,
        "start_date": ad.start_date.isoformat() if ad.start_date else None,
        "end_date": ad.end_date.isoformat() if ad.end_date else None,
        "first_shown_date": ad.first_shown_date.isoformat() if ad.first_shown_date else None,
        "last_shown_date": ad.last_shown_date.isoformat() if ad.last_shown_date else None,
        "rank": ad.rank,
        "display_rank": ad.display_rank,
        "ctr_rank": ad.ctr_rank,
        "impression_count": ad.impression_count,
        "spend": ad.spend,
        "likes": ad.likes,
        "budget_level": ad.budget_level,
        "region": ad.region,
        "advertiser_location": ad.advertiser_location,
        "creative_url": ad.creative_url,
        "image_url": ad.image_url,
        "landing_page": ad.landing_page,
        "landing_domain": ad.landing_domain,
        "call_to_action": ad.call_to_action,
        "variant_count": ad.variant_count,
        "query": ad.query,
        "first_seen": ad.first_seen.isoformat() if ad.first_seen else None,
        "last_seen": ad.last_seen.isoformat() if ad.last_seen else None,
    }


def _parse_search_query(query: str | None) -> tuple[str | None, str | None]:
    if not query:
        return None, None
    raw = query.strip()
    lowered = raw.casefold()
    for prefix in ("page:", "fbpage:", "meta-page:"):
        if lowered.startswith(prefix):
            return "meta_page", raw[len(prefix):].strip()
    return "keyword", raw


def _query_ads(query: Optional[str] = None, platform: Optional[str] = None) -> list[dict]:
    db = SessionLocal()
    try:
        ads_query = db.query(Ad)
        search_mode, search_term = _parse_search_query(query)
        if search_term:
            needle = f"%{search_term.lower()}%"
            if search_mode == "meta_page":
                ads_query = ads_query.filter(Ad.platform == "Meta")
                ads_query = ads_query.filter(
                    or_(
                        func.lower(func.coalesce(Ad.advertiser_name, "")).like(needle),
                        func.lower(func.coalesce(Ad.brand_name, "")).like(needle),
                        func.lower(func.coalesce(Ad.page_name, "")).like(needle),
                        func.lower(func.coalesce(Ad.creative_url, "")).like(needle),
                    )
                )
            else:
                ads_query = ads_query.filter(
                    or_(
                        func.lower(func.coalesce(Ad.query, "")).like(needle),
                        func.lower(func.coalesce(Ad.headline, "")).like(needle),
                        func.lower(func.coalesce(Ad.content, "")).like(needle),
                        func.lower(func.coalesce(Ad.content_snippet, "")).like(needle),
                        func.lower(func.coalesce(Ad.advertiser_name, "")).like(needle),
                        func.lower(func.coalesce(Ad.brand_name, "")).like(needle),
                        func.lower(func.coalesce(Ad.page_name, "")).like(needle),
                        func.lower(func.coalesce(Ad.landing_page, "")).like(needle),
                        func.lower(func.coalesce(Ad.landing_domain, "")).like(needle),
                    )
                )
        if platform:
            ads_query = ads_query.filter(Ad.platform == platform)
        ads = ads_query.order_by(Ad.first_seen.desc(), Ad.id.desc()).all()
        return [serialize_ad(ad) for ad in ads]
    finally:
        db.close()


async def run_meta_collection(query: str):
    collector = MetaAPICollector()
    data = await collector.collect(query)
    for raw_ad in data:
        raw_ad["query"] = query
        normalized = normalize_meta_ad(raw_ad)
        if normalized:
            save_ad(normalized)
    print(f"Processed {len(data)} ads for {query} from Meta API")


async def run_tiktok_collection(query: str):
    collector = TikTokCollector(headless=True)
    data = await collector.collect(query)
    for raw_ad in data:
        normalized = normalize_tiktok_ad(raw_ad)
        if normalized:
            save_ad(normalized)
    print(f"Processed {len(data)} ads for {query} from TikTok")


async def run_platform_search(query: str, platforms: Optional[Iterable[str]] = None):
    search_mode, search_term = _parse_search_query(query)
    effective_query = search_term or query
    platform_list = [p.lower() for p in (platforms or ["meta", "tiktok", "google"])]

    if search_mode == "meta_page":
        platform_list = ["meta"]

    if "meta" in platform_list:
        meta_collector = MetaPlaywrightCollector(headless=True)
        meta_results = await meta_collector.collect(effective_query)
        for item in meta_results:
            normalized = normalize_meta_playwright_ad(item)
            if normalized:
                save_ad(normalized)

    if "tiktok" in platform_list:
        tiktok_collector = TikTokCollector(headless=True)
        tiktok_results = await tiktok_collector.collect(effective_query)
        for item in tiktok_results:
            normalized = normalize_tiktok_ad(item)
            if normalized:
                save_ad(normalized)

    if "google" in platform_list:
        google_collector = GoogleAdsCollector(headless=True)
        google_results = await google_collector.collect(effective_query)
        for item in google_results:
            normalized = normalize_google_ad(item)
            if normalized:
                save_ad(normalized)


class ExtensionAd(BaseModel):
    content: str
    platform: str


class ExtensionData(BaseModel):
    ads: List[ExtensionAd]


class SearchRequest(BaseModel):
    query: str
    platforms: List[str] = ["meta", "tiktok", "google"]


@app.post("/collect/extension")
async def collect_extension(data: ExtensionData):
    for index, ad in enumerate(data.ads):
        normalized = normalize_extension_ad(ad.model_dump(), index=index)
        if normalized:
            save_ad(normalized)
    return {"status": f"Saved {len(data.ads)} ads from extension"}


@app.post("/collect/tiktok")
async def collect_tiktok(query: str, background_tasks: BackgroundTasks):
    background_tasks.add_task(run_tiktok_collection, query)
    return {"status": "TikTok collection started in background"}


@app.post("/collect/meta")
async def collect_meta(query: str, background_tasks: BackgroundTasks):
    background_tasks.add_task(run_meta_collection, query)
    return {"status": "Meta collection started in background"}


@app.post("/search")
async def search_ads(request: SearchRequest):
    query = request.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query is required.")

    await run_platform_search(query, request.platforms)
    ads = _query_ads(query=query)
    return {"query": query, "count": len(ads), "ads": ads}


@app.get("/ads")
async def get_ads(
    query: Optional[str] = Query(default=None),
    platform: Optional[str] = Query(default=None),
):
    return _query_ads(query=query, platform=platform)


@app.get("/report")
async def get_report(query: str):
    ads = _query_ads(query=query)
    if not ads:
        raise HTTPException(status_code=404, detail=f"No ads found for query '{query}'.")

    pdf_path = generate_product_pdf(query, ads)
    filename = os.path.basename(pdf_path)
    return FileResponse(pdf_path, media_type="application/pdf", filename=filename)


@app.get("/")
async def root():
    return FileResponse(os.path.join(os.path.dirname(__file__), "index.html"))
