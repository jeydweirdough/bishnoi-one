# Pharmacy

Prescriptions checked, and batches tracked.

**Nothing built yet. This is the shape it will take.**

## Screens

- Rx to check
- Batches
- Expiring soon

## What it keeps

- prescription checks (who checked, when, what they found)
- batches (lot, made, expires, quantity)

## What it asks other modules for

- **crm** — which quotes carry an Rx?
- **inventory** — which product is this a batch of?

A module never reads another module's tables. It asks across a counter — today a
function call, and a web call once either side moves. Anything it needs that is
not listed above is a change to `module.json`, not a quiet import.

## Where the API is

`"api": "shared"` in `module.json`.

`shared` means the one Orbit backend still holds this module's routes and tables,
exactly where they were. It becomes `own` when they move into `api/` here.

## Using it

The shell (`orbit-frontend`) lists this package in `package.json` as
`file:../orbit-pharmacy` and in `transpilePackages`, then re-exports each page from a
route file:

```tsx
export { default, metadata } from "@orbit/pharmacy/screens/<page>";
```

Core — the sheet, the buttons, the fields, `lib/api`, `lib/types`,
`lib/format` — comes from the shell with the usual `@/…` paths.
