# Competitor Ad Research

A lightweight competitor ad intelligence app for collecting and reviewing ads from Meta, TikTok, and Google.

The project includes:
- a FastAPI backend
- a simple dashboard for search and review
- Playwright-based collectors
- SQLite storage for normalized ad records
- PDF export for product-level ad reports

## Current Status

The strongest collector in this repo is `Meta`.

Current platform maturity:
- `Meta`: best-supported and query-driven
- `Google`: partially supported, with weaker result coverage depending on the advertiser/query
- `TikTok`: currently restricted to avoid saving misleading generic results; it needs a true keyword-driven collection flow before it should be considered reliable

## Features

- Search ads by product keyword
- Search Meta ads by Facebook page name using `page: <name>`
- Save normalized ad data to a local SQLite database
- View ads in a browser dashboard
- Export product reports as PDF
- Store richer metadata such as advertiser/page, dates, display rank, CTA, landing page, and region

## Project Structure

```text
backend/
  database.py        SQLAlchemy models and DB initialization
  index.html         Dashboard UI
  main.py            FastAPI app and routes
  reporting.py       PDF generation
  requirements.txt   Python dependencies
  utils.py           Normalization and persistence helpers

collectors/
  base.py
  google_collector.py
  meta_api.py
  meta_playwright.py
  tiktok_collector.py

extension/
  manifest.json
  content.js
  popup.html
  popup.js
```

## Requirements

- Python 3.11+ recommended
- Chromium/Playwright-compatible environment

## Setup

1. Create a virtual environment:

```bash
python3 -m venv venv
```

2. Activate it:

```bash
source venv/bin/activate
```

3. Install dependencies:

```bash
pip install -r backend/requirements.txt
```

4. Install Playwright browsers if needed:

```bash
playwright install chromium
```

## Run the App

Start the FastAPI app:

```bash
uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Open the dashboard:

```text
http://127.0.0.1:8000/
```

## Using the Dashboard

### Product search

Type a product name such as:
- `perfume`
- `raincoat`
- `anti aging cream`

Then press `Enter`.

### Facebook page search

To search by Meta/Facebook page name, use:

- `page: Nike`
- `fbpage: Zara`
- `meta-page: Adidas`

This limits the live search to Meta and filters saved ads by page-related fields.

## API Endpoints

- `GET /`
  Dashboard UI
- `GET /ads?query=<term>&platform=<platform>`
  Fetch saved ads
- `POST /search`
  Run live collection and return matching ads
- `GET /report?query=<term>`
  Generate and download a PDF report
- `POST /collect/meta`
  Background Meta collection
- `POST /collect/tiktok`
  Background TikTok collection
- `POST /collect/extension`
  Save ads captured by the browser extension

## Notes

- The local database file is intentionally ignored in git.
- Generated reports and debug screenshots are intentionally ignored in git.
- Search quality depends heavily on the source platform and how well the collector can target the query.

## Next Improvements

- Build true keyword-targeted TikTok collection
- Improve Google advertiser selection and relevance scoring
- Add better result ranking and filtering in the dashboard
- Add PostgreSQL support for production use

