# Admin

Running one company.

**Its screens are still in `orbit-frontend`, waiting to move in.**

## Screens

- Company
- Apps
- People
- Roles & permissions
- Teams
- Audit log
- Lists
- Pricing
- Money & formats
- Orders
- Retention
- Goals

## What it keeps

- nothing of its own — it edits core's tables

## What it asks other modules for

- ***** — what can be granted in you?

A module never reads another module's tables. It asks across a counter — today a
function call, and a web call once either side moves. Anything it needs that is
not listed above is a change to `module.json`, not a quiet import.

## Where the API is

`"api": "shared"` in `module.json`.

`shared` means the one Orbit backend still holds this module's routes and tables,
exactly where they were. It becomes `own` when they move into `api/` here.

## Using it

The shell (`orbit-frontend`) lists this package in `package.json` as
`file:../orbit-admin` and in `transpilePackages`, then re-exports each page from a
route file:

```tsx
export { default, metadata } from "@orbit/admin/screens/<page>";
```

Core — the sheet, the buttons, the fields, `lib/api`, `lib/types`,
`lib/format` — comes from the shell with the usual `@/…` paths.
