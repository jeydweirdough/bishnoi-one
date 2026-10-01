# Nabhi Pharmacy — screens

The Pharmacy's own Next.js app. Its API is in `../backend`; only this app's
server talks to it, never the browser.

```
cp .env.example .env.local
npm install
npm run dev        # http://localhost:4307
```

## Pages

The sidebar follows the order work moves in. What belongs to a page is a tab
inside it, and each page shows only to a role that may open it.

| Page | Tabs |
|---|---|
| Dashboard | What needs checking, dispensing, and a look at the stock |
| Prescriptions | Inbox · Pending verification · Verified · Rejected / Needs clarification · History. Each opens its **Check Prescription** page |
| Dispensing | Dispensing queue · Partially dispensed · Dispensed · Dispensing history. **New dispensing** picks the batch per medicine |
| Sales | Sales transactions (today) · Sales history · Returns · Refunds; counter sale |
| Patients & customers | Patient records · Customer records; each with Prescription history and Medication history |
| Medicines | Medicine catalog (by status: active, inactive, discontinued) · Categories · Brands; medicine details |
| Batch & expiry | Batch records · Expiring · Expired · Recall / quarantine |
| Stock | Current · Low · Receiving · Adjustment · Movement |
| Suppliers | Suppliers and their deliveries |
| Reports | Prescriptions · Dispensing · Sales · Medicine usage · Expiry · Stock |
| Administration | Users · Roles & permissions · Activity log |

## Where things go

| Path | What it's for |
|---|---|
| `app/(app)/…/page.tsx` | Routes; each re-exports a screen |
| `src/screens/` | One file per page |
| `src/components/` | Forms and the pieces screens share (`bits.tsx`: marks, tabs, tables) |
| `src/actions/pharmacy.ts` | Every change the screens make, as server actions |
| `src/lib/` | Types the API sends, the words for each state, the page helper |
| `src/platform/` | The shell every Nabhi app shares: sign-in, sidebar, UI kit |
