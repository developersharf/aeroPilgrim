# aeroPilgrim (UmrahFly)

AI-powered Umrah flight search and trip-planning assistant built with Django. Search calendar fares from Bangladesh to Saudi Arabia, compare dates, manage watchlists, and get personalized help on every trip — including an n8n-powered chat assistant on the flight details page and an in-app site-wide assistant chat bubble.

**Live demo:** [aeropilgrim-production.up.railway.app](https://aeropilgrim-production.up.railway.app/)

## Features

### Search & data
- **Flight price calendar** — Search routes between Dhaka, Chattogram, Sylhet, Jeddah, and Medina via the [Sky Scrapper](https://rapidapi.com/apiheya/api/sky-scrapper) API (RapidAPI).
- **Smart caching** — A normalized `SearchCache` (hash-addressed) reuses prior API responses so repeat lookups avoid extra calls. The legacy `Search` model still backs the public `/search/flight/<id>/<date>/` URL.
- **Async background searches** — Long-running queries can be dispatched in the background; the SPA polls a status endpoint until results are ready.
- **Search history** — Every successful fresh API call is recorded per user; one-click **Re-run** re-applies the same params from the dashboard.

### Accounts, plans & quota
- **User accounts** — Register, log in, and save searches (results require login).
- **Free vs Premium plans** — Free: **1** live search / day. Premium: **5** live searches / day, plus unlimited cached reruns and watchlists.
- **Demo SSLCommerz gateway** — A sandbox payment flow that flips the user's subscription to Premium immediately — no real card is required.
- **Rolling-24h quota** — Implemented via `SearchUsage` + `UserSubscription.daily_quota`; resets at midnight UTC.
- **Watchlists** — Save a route, budget, stay range, and optional target date. The notify-ready flag marks which watchlists are ready for follow-up.

### AI assistance
- **AI travel actions** — One-click prompts on the trip details page for booking plans, hotels, itineraries, and budget breakdowns (OpenAI or built-in fallbacks).
- **n8n trip assistant** — Custom glass-style chat on the flight details page, proxied through Django to your n8n workflow with full trip context from the database. Responses are English-only.
- **Site-wide assistant** — Floating chat bubble (bottom-right) powered by an n8n webhook, available on every page.

### Bot APIs for n8n
- **Bot Search** — Run flight searches from your n8n workflow with a shared secret key.
- **Bot Trip Context** — Pull the full trip record (route, selected price, cheaper alternatives, calendar size, stay length, …) from the database.

### UX
- **Single-page dashboard** — `/dashboard/` is a SPA powered by vanilla JS that hits the JSON API endpoints. The nav username links straight to it.
- **Glass-card design system** — Global `umrahfly.css` with `glass-card`, `apple-input`, `apple-btn`, `card-title`, `uf-form` / `uf-field` / `uf-range` / `uf-toggle`, `uf-list` / `.empty`, `uf-feature-list`, badges, and a Phosphor-Icons + Tailwind CDN stack.
- **Responsive layout** — Forms collapse to a single column under 640 px; nav links collapse to icons on mobile.

## Project structure

```
aeroPilgrim/
├── manage.py
├── requirements.txt
├── Dockerfile
├── start.sh                    # Docker / Railway entrypoint
├── .env.example
├── core/                       # Main Django app
│   ├── models.py               # Search, SearchCache, SearchRateLimit,
│   │                           # UserSubscription, SearchUsage, Watchlist,
│   │                           # PaymentTransaction, AsyncSearchJob,
│   │                           # SearchHistory
│   ├── views.py
│   ├── urls.py
│   ├── forms.py
│   ├── context_processors.py   # n8n_chat, subscription
│   ├── admin.py
│   └── services/
│       ├── flight_api.py            # Sky Scrapper API + airport lookup
│       ├── rate_limit.py            # IP cooldown + cache helpers
│       ├── search_orchestrator.py   # quota, params, run_search
│       ├── async_search.py          # background job dispatch
│       ├── payment_service.py       # demo SSLCommerz init/confirm/cancel
│       ├── ai_service.py            # OpenAI action buttons
│       ├── chat_service.py          # Trip context builder (DB)
│       └── n8n_chat_service.py      # n8n webhook proxy
├── templates/
│   ├── base.html               # Global nav, page shell, chat bubble
│   └── core/
│       ├── home.html
│       ├── search_results.html
│       ├── flight_detail.html  # Trip page + n8n chat UI
│       ├── login.html
│       ├── register.html
│       ├── dashboard.html      # SPA dashboard
│       ├── pricing.html        # Free vs Premium cards
│       ├── payment_demo.html   # Sandbox gateway
│       └── payment_result.html # Success / cancelled / failed
├── static/
│   ├── css/umrahfly.css        # Glass design system
│   ├── js/umrahfly.js
│   ├── js/dashboard.js         # SPA behaviour
│   ├── fonts/                  # Breite Grotesk + Commit Mono
│   └── videos/                 # Background video
└── search/                     # Django project settings
    ├── settings.py
    ├── urls.py
    └── wsgi.py
```

## Local development

1. Create and activate a virtual environment:

```bash
python -m venv env
source env/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Create your environment file:

```bash
cp .env.example .env
```

Edit `.env` and add your API keys (see table below).

4. Run migrations and start the server:

```bash
python manage.py migrate
python manage.py runserver
```

Open [http://127.0.0.1:8000/](http://127.0.0.1:8000/).

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SECRET_KEY` | Yes | Django secret key |
| `DEBUG` | Yes | `True` locally, `False` on Railway |
| `FLIGHT_API_KEY` | Yes | RapidAPI key for Sky Scrapper |
| `FLIGHT_API_HOST` | Yes | `sky-scrapper.p.rapidapi.com` |
| `N8N_CHAT_WEBHOOK_URL` | For chat | n8n chat webhook URL (used by both the trip-details assistant and the site-wide bubble) |
| `BOT_API_KEY` | For n8n bots | Shared secret for `/api/bot-*` endpoints |
| `OPENAI_API_KEY` | Optional | Powers AI action buttons on trip details |
| `AI_MODEL` | Optional | Defaults to `gpt-4o-mini` |
| `DATABASE_URL` | Optional | Neon Postgres URL; omit to use local SQLite |
| `CONN_MAX_AGE` | Optional | DB connection pool age in seconds (default `30`) |
| `ALLOWED_HOSTS` | Production | Comma-separated hosts (Railway env) |
| `CSRF_TRUSTED_ORIGINS` | Production | Full origin URLs with `https://` |

## Main routes

### Pages

| Path | Description |
|------|-------------|
| `/` | Home — flight search form |
| `/search/` | Search results (login required) |
| `/search/flight/<id>/<date>/` | Trip details + n8n chat assistant |
| `/dashboard/` | Single-page dashboard (quota, search form, history, watchlists) |
| `/pricing/` | Free vs Premium plan comparison |
| `/pricing/upgrade/` | POST — kicks off demo payment |
| `/payment/demo/<tran_id>/` | Sandbox payment page |
| `/payment/demo/<tran_id>/callback/` | Sandbox payment callback |
| `/payment/result/<tran_id>/` | Success / cancelled / failed screen |
| `/register/` `/login/` `/logout/` | Auth |

### AI + chat endpoints

| Path | Description |
|------|-------------|
| `/search/flight/<id>/<date>/ai/` | AI action button endpoint (POST, login required) |
| `/search/flight/<id>/<date>/chat/` | n8n trip-assistant proxy (POST, login required) |

### Search + dashboard JSON API (login required)

| Path | Description |
|------|-------------|
| `/api/search/` | POST — run a search synchronously |
| `/api/search/async/` | POST — dispatch a search in the background |
| `/api/search/status/<job_id>/` | GET — poll async job status |
| `/api/history/` | GET — list the user's recent searches |
| `/api/history/<history_id>/rerun/` | POST — re-run a previous search |
| `/api/watchlists/` | GET — list watchlists |
| `/api/watchlists/create/` | POST — create a watchlist |
| `/api/watchlists/<pk>/update/` | POST — update a watchlist |
| `/api/watchlists/<pk>/delete/` | POST — delete a watchlist |

### Bot APIs for n8n

Both endpoints require the header:

```
X-Bot-Api-Key: <your BOT_API_KEY>
```

**Search flights**

```
GET /api/bot-search/?from_city=DAC&to_city=MED&stay_days=7&timespan_to_search=30
```

**Get trip context from database**

```
GET /api/bot-trip-context/?search_id=3&flight_date=2026-06-29
```

Returns route, selected price, cheaper alternative dates, calendar size, stay length, and more.

The flight-details chat sends the same trip fields to your n8n webhook on each message, with an English-only instruction, so your workflow can call these APIs when it needs live data.

## Data model (overview)

| Model | Purpose |
|-------|---------|
| `Search` | Legacy per-call persisted search; backs `/search/flight/<id>/<date>/`. |
| `SearchCache` | Normalized, hash-addressed cache used by the orchestrator (`SearchCache.build_query_hash`). TTL = 24 h. |
| `SearchRateLimit` | IP-level cooldown for external API calls (one new call / IP / week by default). |
| `UserSubscription` | Free vs Premium, `daily_quota`, expiry. Created on demand. |
| `SearchUsage` | One row per real API call; used to enforce rolling-24h quota. |
| `Watchlist` | User-saved route + budget + stay range + notify flag. |
| `PaymentTransaction` | Demo SSLCommerz transactions (`pending` / `success` / `failed` / `cancelled`). |
| `AsyncSearchJob` | Background job tracker (`queued` / `running` / `completed` / `failed`). |
| `SearchHistory` | Per-user persisted search history with cheapest price/date summary. |

## Context processors

Both are wired in `TEMPLATES.OPTIONS.context_processors` and run on every request:

- `core.context_processors.n8n_chat` — exposes `N8N_CHAT_WEBHOOK_URL` so the chat-bubble JS can POST directly.
- `core.context_processors.subscription` — exposes `subscription`, `is_premium_user`, `quota_used`, `quota_total`, `plan_label` so the nav badge and dashboard render without view-side lookups.

## Docker

Build and run locally:

```bash
docker build -t aeropilgrim .
docker run -p 8000:8000 --env-file .env aeropilgrim
```

The container runs `start.sh`, which:

1. Applies migrations
2. Collects static files
3. Starts Gunicorn on port `8000` (or Railway's `$PORT`)

## Deploy on Railway

1. Push this repo to GitHub.
2. Create a new Railway project from the GitHub repo.
3. Railway detects the `Dockerfile` and builds automatically.
4. Add these variables in Railway **Variables** (do not commit `.env`):

```
SECRET_KEY=your-strong-secret
DEBUG=False
ALLOWED_HOSTS=your-app.up.railway.app
CSRF_TRUSTED_ORIGINS=https://your-app.up.railway.app
FLIGHT_API_KEY=your-key
FLIGHT_API_HOST=sky-scrapper.p.rapidapi.com
N8N_CHAT_WEBHOOK_URL=https://your-n8n-instance/webhook/.../chat
BOT_API_KEY=your-bot-secret
OPENAI_API_KEY=your-openai-key   # optional
AI_MODEL=gpt-4o-mini              # optional
DATABASE_URL=postgresql://USER:PASSWORD@HOST/DBNAME?sslmode=require
CONN_MAX_AGE=30
```

5. Deploy. Railway sets `PORT` automatically — Gunicorn binds to it via `start.sh`.

## Common commands

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py collectstatic
python manage.py test
python manage.py check
```

## Contributors

- [Muhammad Sharf Uddin](https://github.com/developersharf)
- [Ayon914](https://github.com/Ayon914)
- [AbdulAlBinShahin](https://github.com/AbdulAlBinShahin)

## License

MIT — see [LICENSE](LICENSE).
