# Competitor Ad Research Automation

## Setup

1. **Install Dependencies:**
   ```bash
   pip install -r backend/requirements.txt
   playwright install chromium
   ```

2. **Run Backend:**
   Ensure you are in the `competitor-ad-research` directory, then run:
   ```bash
   export PYTHONPATH=$PYTHONPATH:.
   uvicorn backend.main:app --reload
   ```

3. **Configure Environment:**
   Create a `.env` file in the root with:
   ```
   META_ACCESS_TOKEN=your_token_here
   DATABASE_URL=sqlite:///./ad_intelligence.db
   ```

## Project Structure

- `backend/`: FastAPI application and database models.
- `collectors/`: Logic for Meta, TikTok, and Google collectors.
- `extension/`: Placeholder for Chrome extension.
- `data/`: Raw storage for captured creatives.

## Status

- Phase 1 (Meta API): Initial implementation complete.
- Phase 2 (Meta Playwright): Initial implementation complete.
- Phase 3 (TikTok Collector): Initial implementation complete.
- Phase 4 (Google Collector): Pending.
- Phase 5 (Extension & Dashboard): Pending.
