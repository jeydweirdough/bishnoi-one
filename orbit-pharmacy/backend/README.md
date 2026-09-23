# Orbit Pharmacy — API

The Pharmacy app's own backend. Its screens are in `../frontend`.

## Running it

```
cp .env.example .env
uv sync
uv run main.py          # http://127.0.0.1:8307  (docs at /docs)
uv run pytest
```

## Settings (`.env`)

| Setting | What it is | Default |
|---|---|---|
| `DATABASE_URL` | This app's own database | `sqlite:///.data/pharmacy.db` |
| `ALLOWED_HOSTS` | Host names this API answers to | `["localhost", "127.0.0.1"]` |
| `CORS_ORIGINS` | Browser origins allowed to call it directly | none |

## Where things go

| Path | What it's for |
|---|---|
| `app/routers/pharmacy.py` | The endpoints, under `/pharmacy` |
| `app/config.py` | Settings read from `.env` |
| `app/main.py` | Builds the app: security headers, allowed hosts, routers |
| `tests/` | Tests (`uv run pytest`) |

Port: screens on 4307, this API on 8307 (screens + 4000).
