# Orbit — the API

Every Orbit app talks to this one server. The apps hold the screens; this holds
the people, the companies, the permissions and the records, and it is the only
thing that decides who may see what.

```
orbit-admin ─┐
orbit-sales ─┤
orbit-finance ─┼──→  this API  :8000  ──→  one database
orbit-inventory ─┤
orbit-platform ─┤
the Orders app ─┘
```

## Running it

```
python main.py          # with .venv activated
uv run main.py
uv run main.py --port 8001
```

Serves on **8000**. Every app's `.env.local` points at it with
`API_URL=http://127.0.0.1:8000`, and the Orders app with `ORBIT_API_URL`.

## Ports

One port each, so they can all run at once. An app takes its own with
`npm run dev` in its folder.

| Port | App | Folder | Built? |
|------|-----|--------|--------|
| **8000** | the API | `orbit-backend` | yes |
| **4300** | Executive Admin | `orbit-admin` | yes |
| 4301 | — free | — | was Analytics, removed |
| **4302** | Sales | `orbit-sales` | yes |
| **4303** | Finance | `orbit-finance` | yes |
| **4304** | Inventory | `orbit-inventory` | yes |
| **4305** | Platform *(Developer Admin)* | `orbit-platform` | yes |
| 4306 | Licensing | `orbit-in-licensing` | stub — no dev script |
| 4307 | Pharmacy | `orbit-pharmacy` | stub — no dev script |
| 4308 | Regulatory | `orbit-regulatory` | stub — no dev script |
| **4000** | Orders *(the Discord app)* | `getmeds_discord_system` | yes, separate repo |

Nothing is meant to sit on **3000–3005**. Those were the old ports, and 3000 in
particular is the first thing any other tool on the machine takes, which is why
everything moved up here.

One clash to know about: `orbit-frontend` — the old all-in-one shell, kept only
until its folder can be removed — still has `next dev --port 4306`, which is
Licensing's. Nothing runs it, but if anyone does while Licensing is up, one of
them will not start.

### Ports are written down twice

The port a browser reaches an app on comes from its own `package.json`:

```json
"dev": "next dev --port 4303"
```

The address the *other* apps use to link to it comes from `DEFAULTS` in each
app's `src/platform/lib/apps.ts`. Those two have to agree, and nothing checks
that they do — if you move an app, change both.

Each app carries its own copy of that file (they were vendored so every app
stands alone), so a port change is one edit per app, not one edit.
`NEXT_PUBLIC_ORBIT_<APP>_URL` overrides it per deployment.

## One sign-in, every app

The API issues a token and never sets a cookie. Each Next server puts it in
`crm_session` itself — host-only, no `domain`. Cookies ignore the port, so
`localhost:4302` and `localhost:4303` share one jar: signing in to any app signs
you in to all of them.

That is deliberate, and it is why an app checks on **every** request whether it
is yours, not only at its sign-in page. Arriving at an app that is not yours
sends you to that app's `/login?denied=1`, which says so.

On a real domain this stops being free. Subdomains need `domain=".example.com"`
on the cookie; separate domains cannot share one at all, which is what
`/sso/authorize` exists for.
