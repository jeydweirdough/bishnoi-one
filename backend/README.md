# Orbit Finance — API

The Finance app's own backend. Its screens are in `../frontend`.

## Running it

```
cp .env.example .env
uv sync
uv run main.py          # http://127.0.0.1:8303  (docs at /docs)
uv run pytest
```

## Settings (`.env`)

| Setting | What it is | Default |
|---|---|---|
| `DATABASE_URL` | This app's own database | `sqlite:///.data/finance.db` |
| `ALLOWED_HOSTS` | Host names this API answers to | `["localhost", "127.0.0.1"]` |
| `CORS_ORIGINS` | Browser origins allowed to call it directly | none |

## Where things go

| Path | What it's for |
|---|---|
| `app/routers/finance.py` | The endpoints, under `/finance` |
| `app/config.py` | Settings read from `.env` |
| `app/main.py` | Builds the app: security headers, allowed hosts, routers |
| `tests/` | Tests (`uv run pytest`) |

Port: screens on 4303, this API on 8303 (screens + 4000).
