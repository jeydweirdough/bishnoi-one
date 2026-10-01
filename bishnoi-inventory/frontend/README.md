# Bishnoi One Inventory — screens

What you have, where it is, how much you have, what is moving, and what needs
attention. The API is in `../backend`.

```
cp .env.example .env.local
npm install
npm run dev        # http://localhost:4304
```

## Screens

| Place | Tabs |
|---|---|
| Dashboard, Alerts | |
| Products | Products (with variants, specifications, pictures, supplier prices) · Categories · Brands · Units of measure |
| Stock | Stock overview · Movements · Batches & expiry · Serial numbers |
| Transfers | |
| Adjustments & counts | Adjustments · Inventory counts |
| Warehouses | each with its locations |
| Purchase orders | Purchase orders · Receiving · Backorders |
| Suppliers | |
| Orders & issuance | Orders · Reservations · Issuance history |
| Reports | 16 reports, each exportable to CSV |
| Users & roles, Activity log | |

The sidebar shows each person only the places their role opens; the API
checks every permission again.

## Where things go

| Path | What it's for |
|---|---|
| `app/(app)/…/page.tsx` | Routes. Each points at its screen in `src/screens` |
| `src/screens/` | The screens (server components) |
| `src/components/` | Forms and pieces the screens share |
| `src/actions/inventory.ts` | Every change, as a server action. The browser never talks to the API |
| `src/lib/types.ts`, `src/lib/labels.ts` | What the API sends, and its words |
| `src/platform/` | The frame every Bishnoi One app shares (sidebar, sign-in, UI kit) |
