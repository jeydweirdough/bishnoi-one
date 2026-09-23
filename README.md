# Inventory

What the company sells, and what it costs.

**Its screens are still in `orbit-frontend`, waiting to move in.**

## Screens

- Products
- Prices
- Promos
- Bundles

## What it keeps

- products
- product_prices
- price_types
- division_pricing
- division_price_types
- promos
- promo_products
- promo_divisions
- promo_tiers
- bundles
- bundle_items
- bundle_divisions
- pricing_settings
- gl_issuers

## What it asks other modules for

- nothing

A module never reads another module's tables. It asks across a counter — today a
function call, and a web call once either side moves. Anything it needs that is
not listed above is a change to `module.json`, not a quiet import.

## Where the API is

`"api": "shared"` in `module.json`.

`shared` means the one Orbit backend still holds this module's routes and tables,
exactly where they were. It becomes `own` when they move into `api/` here.

## Using it

The shell (`orbit-frontend`) lists this package in `package.json` as
`file:../orbit-inventory` and in `transpilePackages`, then re-exports each page from a
route file:

```tsx
export { default, metadata } from "@orbit/inventory/screens/<page>";
```

Core — the sheet, the buttons, the fields, `lib/api`, `lib/types`,
`lib/format` — comes from the shell with the usual `@/…` paths.
