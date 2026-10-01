# CRM

Customers, and everything that happens with them.

**Its screens are still in `bishnoi-frontend`, waiting to move in.**

## Screens

- Overview
- Customers
- Follow-ups
- Quotes
- Retention
- Prices

## What it keeps

- customers
- activities
- follow-ups
- quotes
- retention_rules
- team_prices
- team_price_types

## What it asks other modules for

- **inventory** — what does this product cost?

A module never reads another module's tables. It asks across a counter — today a
function call, and a web call once either side moves. Anything it needs that is
not listed above is a change to `module.json`, not a quiet import.

## Where the API is

`"api": "shared"` in `module.json`.

`shared` means the one Bishnoi One backend still holds this module's routes and tables,
exactly where they were. It becomes `own` when they move into `api/` here.

## Using it

The shell (`bishnoi-frontend`) lists this package in `package.json` as
`file:../bishnoi-crm` and in `transpilePackages`, then re-exports each page from a
route file:

```tsx
export { default, metadata } from "@bishnoi/crm/screens/<page>";
```

Core — the sheet, the buttons, the fields, `lib/api`, `lib/types`,
`lib/format` — comes from the shell with the usual `@/…` paths.
