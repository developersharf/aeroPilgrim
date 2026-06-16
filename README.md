# aeroPilgrim

AI-powered Umrah flight search and booking assistant built with Django.

## Project structure

```
Umrah/
├── manage.py              # Run all Django commands from here
├── requirements.txt
├── Dockerfile
├── start.sh               # Used by Docker / Railway
├── .env.example           # Copy to .env for local development
├── core/                  # Main Django app
│   ├── models.py
│   ├── views.py
│   ├── urls.py
│   ├── forms.py
│   └── services/
│       ├── flight_api.py
│       └── ai_service.py
├── templates/             # HTML templates
│   ├── base.html
│   └── core/
├── static/                # CSS, JS, images, fonts
└── search/                # Django project config only
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

Edit `.env` and add your API keys.

4. Run migrations and start the server:

```bash
python manage.py migrate
python manage.py runserver
```

Open `http://127.0.0.1:8000/`.

## Environment variables

| Variable | Description |
|----------|-------------|
| `SECRET_KEY` | Django secret key |
| `DEBUG` | `True` locally, `False` on Railway |
| `ALLOWED_HOSTS` | Comma-separated hosts, e.g. `localhost,127.0.0.1,.railway.app` |
| `CSRF_TRUSTED_ORIGINS` | e.g. `https://your-app.up.railway.app` |
| `FLIGHT_API_KEY` | RapidAPI key for Sky Scrapper |
| `FLIGHT_API_HOST` | `sky-scrapper.p.rapidapi.com` |
| `OPENAI_API_KEY` | Optional, for AI recommendations |
| `AI_MODEL` | Optional, defaults to `gpt-4o-mini` |

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
3. Railway will detect the `Dockerfile` and build automatically.
4. Add these variables in Railway **Variables** (do not commit `.env`):

```
SECRET_KEY=your-strong-secret
DEBUG=False
ALLOWED_HOSTS=your-app.up.railway.app
CSRF_TRUSTED_ORIGINS=https://your-app.up.railway.app
FLIGHT_API_KEY=your-key
FLIGHT_API_HOST=sky-scrapper.p.rapidapi.com
```

5. Deploy. Railway sets `PORT` automatically — Gunicorn binds to it via `start.sh`.

## Common commands

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py collectstatic
python manage.py test
```

## License

MIT — see [LICENSE](LICENSE).
