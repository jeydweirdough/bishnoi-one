# Bishnoi One Platform — screens

The control tower above every Bishnoi One application. It doesn't run the pharmacy,
the CRM or the inventory; it answers "what is happening across the whole
platform right now?" and lets the people who run the platform act on it.

Its API is `../backend` (see its README for every endpoint).

## Running it

```
cp .env.example .env.local
npm install
npm run dev             # http://localhost:4305
```

`API_URL` in `.env.local` points at the API (port 8305). Sign in with a staff
account made by the backend's users tool; in development,
`uv run python -m app.tools.users demo` in `../backend` makes demo accounts
and sample records.

## What's where

| Sidebar | Page | What it's for |
|---|---|---|
| Dashboard | `/` | Everything at once: counts, health, traffic, support, incidents |
| Companies | `/companies`, `/companies/[id]` | Every company, its departments and branches, its applications |
| Users | `/users`, `/users/[id]` | The people at the companies, and which applications each may use |
| Access | `/access` | Access requests, the company × application matrix, roles and permissions, staff |
| Applications | `/applications`, `/applications/[id]` | The registry, versions and deployments, integrations |
| Monitoring | `/monitoring` | Platform, application, API, database and integration health; traffic |
| Incidents | `/incidents`, `/incidents/[id]` | Something broken for many, now |
| Support | `/support`, `/support/[id]` | Complaints, bugs, system issues, feature requests, support tickets |
| Activity & audit | `/activity` | Everything done on the platform, by category |
| Communications | `/communications` | Announcements, system notifications, maintenance notices |
| Settings | `/settings` | Platform, monitoring, notification and security settings |

Everyone signed in (staff) sees everything. **Support** works tickets and
incidents; changing the platform itself takes a **Platform Admin**, and the
screens hide what the API would refuse.

## Where things go

| Path | What it's for |
|---|---|
| `app/(app)/…` | The pages |
| `src/actions/` | Server actions, one file per area |
| `src/components/` | The console's own components; `marks.tsx` for statuses and tabs |
| `src/lib/types.ts`, `src/lib/words.ts` | The API's shapes; the words for its codes |
| `src/lib/pages.ts` | The sidebar's places |
| `src/platform/` | The frame every Bishnoi One app shares (sign-in, sidebar, UI parts) |
