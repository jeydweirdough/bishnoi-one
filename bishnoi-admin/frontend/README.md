# Admin

Running one company.

**Its screens are still in `bishnoi-frontend`, waiting to move in.**

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

`shared` means the one Bishnoi One backend still holds this module's routes and tables,
exactly where they were. It becomes `own` when they move into `api/` here.

## Using it

The shell (`bishnoi-frontend`) lists this package in `package.json` as
`file:../bishnoi-admin` and in `transpilePackages`, then re-exports each page from a
route file:

```tsx
export { default, metadata } from "@bishnoi/admin/screens/<page>";
```

Core — the sheet, the buttons, the fields, `lib/api`, `lib/types`,
`lib/format` — comes from the shell with the usual `@/…` paths.
