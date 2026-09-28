# Campus Customs Shop + AI Shop Assistant (hw4)

A Campus Customs–style Yale merch store with a shop-assistant chatbot.

- **Frontend:** React + Vite + TypeScript (`frontend/`)
- **Backend:** FastAPI (`backend/main.py`)
- **Agent:** one PydanticAI agent (OpenAI via Portkey, `gpt-5.6-luna`) that answers price and stock questions from the local database, puts matching products on the page, remembers logged-in shoppers, and sets restock alerts.

**The agent is four files in `backend/`:**
- `prompts/prompt.md`: system prompt, voice, safety rules
- `agent.py`: model, agent, double-check validator, audit record
- `tools.py`: 10 tools, plus audit-trail and restock storage helpers
- `models.py`: Pydantic types

The other backend files (`auth.py`, `db.py`, `chat_store.py`) are web-app plumbing for accounts, SQLite and saved chats.

## Layout
```
hw4/
├── AI_prompts.md            # log of prompts typed into the vibe coder
├── requirements.txt         # backend deps (requirements-dev.txt adds Playwright for the app check)
├── .env.example             # copy to .env and add your key
├── .gitignore
├── README.md
├── frontend/                # Vite React TypeScript app
├── backend/
│   ├── main.py              # FastAPI app: run with `uvicorn main:app --reload --port 8000`
│   ├── agent.py  models.py  tools.py
│   ├── prompts/prompt.md
│   └── auth.py  db.py  chat_store.py
├── scripts/capture_app_check.py   # Playwright screenshots for output/app_check.html
└── output/
    ├── harness.md           # how the whole system works (start here)
    ├── design.md  usability.md  site_research.md
    ├── app_check.html       # double-click to open
    ├── app_check_images/    # screenshots linked from app_check.html
    └── audit_trail.json     # append-only log of agent runs (shopper messages redacted)
```

## 1. Place the data pack (not in git)
The database and product photos are private and git-ignored. Put them here:
```
hw4/data/
├── campus_customs.db
└── products/            # <product_id>.jpg images referenced by the catalogue
```
On first start, the backend adds its own tables (`sessions`, `restock_alerts`) and an index to the database.

## 2. Add your API key
```bash
cp .env.example .env
```
Then edit `.env` and set `PORTKEY_API_KEY=...`.

## 3. Run the backend (terminal 1)
Requires Python 3.12+.
```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cd backend
source ../.venv/bin/activate
uvicorn main:app --reload --port 8000
```
Check it with http://localhost:8000/api/health → `{"status":"ok"}`.

## 4. Run the frontend (terminal 2)
Requires Node 20+.
```bash
cd frontend
npm install
npm run dev
```
Open **http://localhost:5173**. Vite proxies `/api` and `/media` to the backend on :8000.

**Test login** (seed user): `test@campuscustoms.yale.edu` / `password`

## Optional: app check screenshots
With both servers running:
```bash
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m playwright install chromium   # first time only
.venv/bin/python scripts/capture_app_check.py
```
Then open `output/app_check.html`.

## Docs
- `output/harness.md`: architecture, data, models (and why each field), tools, safety rules, specs (loop limits, result caps, models), audit trail, API, and how to run
- `output/usability.md` · `output/design.md` · `output/app_check.html`

Class project demo, not affiliated with or endorsed by Campus Customs or Yale University. No real orders or payments.
