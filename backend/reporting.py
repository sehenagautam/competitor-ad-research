from __future__ import annotations

import os
import re
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas


REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports"


def safe_slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "report"


def _wrap_text(text: str, font_name: str, font_size: int, max_width: float) -> list[str]:
    words = text.split()
    if not words:
        return [""]

    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if stringWidth(candidate, font_name, font_size) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def generate_product_pdf(query: str, ads: list[dict]) -> str:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / f"{safe_slug(query)}-ads.pdf"

    pdf = canvas.Canvas(str(path), pagesize=letter)
    width, height = letter
    margin = 0.6 * inch
    y = height - margin

    def new_page():
        nonlocal y
        pdf.showPage()
        y = height - margin

    pdf.setTitle(f"{query} Ad Report")
    pdf.setFont("Helvetica-Bold", 20)
    pdf.drawString(margin, y, f"Ad Research Report: {query}")
    y -= 0.35 * inch

    pdf.setFont("Helvetica", 11)
    pdf.drawString(margin, y, f"Ads captured: {len(ads)}")
    y -= 0.3 * inch

    max_width = width - (2 * margin)

    for index, ad in enumerate(ads, start=1):
        if y < 1.8 * inch:
            new_page()

        pdf.setFont("Helvetica-Bold", 13)
        pdf.drawString(margin, y, f"{index}. {ad.get('headline') or 'Untitled Ad'}")
        y -= 0.2 * inch

        pdf.setFont("Helvetica", 10)
        metadata = [
            f"Platform: {ad.get('platform') or 'N/A'}",
            f"Advertiser: {ad.get('advertiser_name') or ad.get('page_name') or 'N/A'}",
            f"Query: {ad.get('query') or 'N/A'}",
            f"Objective: {ad.get('objective') or 'N/A'}",
            f"Category: {ad.get('category') or 'N/A'}",
            f"Format: {ad.get('ad_format') or 'N/A'}",
            f"Display Rank: {ad.get('display_rank') or 'N/A'}",
            f"CTR Rank: {ad.get('ctr_rank') or 'N/A'}",
            f"Likes: {ad.get('likes') or 'N/A'}",
            f"Budget: {ad.get('budget_level') or 'N/A'}",
            f"Landing Domain: {ad.get('landing_domain') or 'N/A'}",
        ]

        for item in metadata:
            pdf.drawString(margin, y, item)
            y -= 0.16 * inch

        content = ad.get("content_snippet") or ad.get("content") or ""
        pdf.setFont("Helvetica-Oblique", 10)
        for line in _wrap_text(f"Copy: {content}", "Helvetica-Oblique", 10, max_width):
            if y < 1.0 * inch:
                new_page()
                pdf.setFont("Helvetica-Oblique", 10)
            pdf.drawString(margin, y, line)
            y -= 0.16 * inch

        links = [
            ("Creative URL", ad.get("creative_url")),
            ("Landing Page", ad.get("landing_page")),
            ("Image URL", ad.get("image_url")),
        ]
        pdf.setFont("Helvetica", 9)
        for label, value in links:
            if not value:
                continue
            for line in _wrap_text(f"{label}: {value}", "Helvetica", 9, max_width):
                if y < 1.0 * inch:
                    new_page()
                    pdf.setFont("Helvetica", 9)
                pdf.drawString(margin, y, line)
                y -= 0.15 * inch

        y -= 0.12 * inch
        pdf.line(margin, y, width - margin, y)
        y -= 0.18 * inch

    pdf.save()
    return str(path)
