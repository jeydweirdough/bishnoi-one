# In-Licensing

Products being taken on from a principal.

**Nothing built yet. This is the shape it will take.**

## Screens

- Principals
- Under negotiation
- Agreements & their dates

## What it keeps

- principals
- agreements
- renewal dates

## What it asks other modules for

- **inventory** — once a deal lands, the product exists

A module never reads another module's tables. It asks across a counter — today a
function call, and a web call once either side moves. Anything it needs that is
not listed above is a change to `module.json`, not a quiet import.

## Where the API is

`"api": "shared"` in `module.json`.

`shared` means the one Nabhi backend still holds this module's routes and tables,
exactly where they were. It becomes `own` when they move into `api/` here.

## Using it

The shell (`nabhi-frontend`) lists this package in `package.json` as
`file:../nabhi-in-licensing` and in `transpilePackages`, then re-exports each page from a
route file:

```tsx
export { default, metadata } from "@nabhi/in-licensing/screens/<page>";
```

Core — the sheet, the buttons, the fields, `lib/api`, `lib/types`,
`lib/format` — comes from the shell with the usual `@/…` paths.
