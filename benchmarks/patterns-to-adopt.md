# Patterns to adopt

How every Bishnoi One app is built, whichever app it is. Each pattern names the
benchmark it comes from, where we stand, and which matrix rows it serves.

A pattern marked **rule** is how we already build. A pattern marked
**adopted** has been decided and is built to from now on. A pattern marked
**proposed** waits for its matrix row's decision in
[benchmark-matrix.md](benchmark-matrix.md) before anyone builds to it.

---

## P1. One timeline, for any record · proposed · C1, C2, B3

**From:** Odoo's `mail.thread`: a record joins the timeline and gets messages,
followers, scheduled activities and tracked-field changes, with nothing
written per record type.

**For us:** one timeline table linked to *any* record by type and id (a
polymorphic link), not a column per parent (`company_id`, `contact_id`…). A
new kind of record joins it without a migration to the timeline.

**Cost lesson (Salesforce):** track changes to *chosen* fields only. Logging
everything is expensive and buries what matters.

**Today:** CRM activities hang off companies and contacts only; every app's
audit log names changed fields but not their values.

## P2. One filter, shown as table, board or chart · proposed · E1, E2

**From:** Odoo's view types over one action and domain; Salesforce's list ↔
kanban toggle.

**For us:** a list is a saved filter (stored as data, not code) plus a view.
Switching between table, board and chart keeps the filter. A board groups by
a field that has states (status, stage); a chart counts or sums over it.

**Today:** tables only; charts only on fixed report screens.

## P3. Activities ≠ notes ≠ calendar events · proposed · C2

**From:** Odoo's `mail.activity`.

**For us:** an **activity** is something to do: a type, a due date, an
assignee, a link to its record, and done or not. A **note** is something
said, with no due date. A **calendar event** is a time booked. Three kinds of
thing, three shapes; don't fold them into one "activity" with optional
fields.

**Today:** the CRM's activity is the closest (kind, due, done, owner), linked
to companies and contacts only.

## P4. Keyboard paths · proposed · G2

**From:** Marg ERP. Salesforce is *not* the reference here.

**For us:** every high-volume entry screen (order lines, stock receiving,
counter sales, dispensing) can be done start to finish without the mouse:
grid entry, a deliberate tab order, and the same keys doing the same thing
in every app. The test is an operator entering 200 lines an hour.

**Today:** none beyond list selection in the shared kit.

## P5. Validate at entry · rule · A8

**From:** Salesforce validation rules: checked on save, the error attached to
the field it's about.

**For us:** the API checks every rule and names the field that's wrong; the
screen shows the message under that field. The screen may check first for
speed, but the API is the rule.

**Today:** how every app is built.

## P6. Structured interaction record · adopted (ICP) · C4

**From:** Veeva, its strongest idea.

**For us:** a visit or call records *what happened* as fields, not a note:
the products detailed, any order taken, the key messages delivered and the
reaction, validated when it's submitted. A note can never be reported on for
what was said.

**Today:** CRM field visits record an outcome, an amount and a receipt.

## P7. Call plans with attainment · adopted (ICP) · C5

**From:** Veeva.

**For us:** a plan says "visit this account 8 times this quarter", and the
screen shows attainment against it. Activity becomes a plan, not only a log.

**Today:** CRM monthly field goals and performance, but no per-account
frequency.

## P8. Lock what's been submitted · adopted (ICP) · B4

**From:** Veeva's post-submission immutability. Stronger than
archive-never-delete: some records must not change at all after a point.

**For us:** a record that others rely on is locked once submitted, after a
short grace window to fix mistakes. After that, a correction is a new record
that points at the old one, never an edit to it.

**Today:** a verified prescription can't be changed and a recall is final
(Pharmacy); an approved transfer is fixed (Inventory); quote lines keep their
price (CRM). None has a grace window.

## P9. Offline where the field needs it · adopted (D7), in part · G3, G4

**From:** Veeva (offline by design on a connected device); Marg (offline on
the desktop, synced).

**For us (D7, decided 2026-09-25):** logging a **visit** and recording a
**collection** work without signal. They wait on the phone and sync when
there's signal again, and a clash (the same record changed elsewhere) is
flagged for a person to settle, never silently overwritten. Everything else
needs a connection; full offline and van orders are out for now.

**Today:** none.

## P10. Archive, never delete · rule · A3

**For us:** a record with history is switched off, discontinued or closed,
never deleted. The API refuses a delete that would lose history and says what
to do instead.

**Today:** how the CRM, Inventory and Pharmacy are built.

## P11. Two layers of access, checked on the server · rule for the first layer, proposed for the second · B1, B2

**From:** Salesforce's object permissions and record sharing; Odoo's record
rules; SAP's business roles.

**For us:** layer one is what a role may do (`area.action`, one set of
permissions driving both the screens and the API). Layer two is which records
it reaches (own, team, all, or a rule). The server checks both on every
request; hiding a button is never the check.

**Today:** every app has layer one. Only the CRM has layer two (its scopes and
per-division promos and bundles).

## P12. Money, numbers, names · rule

How the apps already agree, kept that way:

- **Money** is in the currency's minor units (centavos), as whole numbers,
  never floats. **Percentages** are basis points (12% is `1200`).
- **Rates that the law sets** (tax) are dated rows, not constants: a change
  in the law is a new row from its start date, and old documents keep theirs.
- **Record numbers** people can say out loud: `PREFIX-YEAR-NUMBER`.
- **Tables** carry their app's prefix (`nbcm_`, `nbin_`, `nbph_`…).
- **Migrations** run on start and each step checks it isn't already done.
- **Apps talk to each other** through their `/integration/…` endpoints,
  with a key per calling app (`INTEGRATION_KEYS` on the app being asked,
  sent in the `X-Bishnoi-Key` header). If the other app can't be reached, the
  caller says so plainly and never saves a half-done record.
- **The shared kit** (`frontend/src/platform/`) is one design across apps: a
  pattern adopted in one app goes into the kit for the rest.

## P13. Associations with labels · adopted · A10, C6

**From:** HubSpot's associations: any record links to any other, both ways,
each link with a label an administrator defines.

**For us:** one association table: from a record (type and id) to a record
(type and id), with a label from a list per pair of types ("Works at",
"Consultant at" for a doctor and a hospital; "Part of" for a hospital and its
group; "Decision maker" for a contact and a deal). Each record page lists its
associations grouped by label, each group with + Add. An activity can be
associated with several records, and shows on each.

**Reach:** an association never lets someone open a record they couldn't
open before; they see that it exists (its name), as with the look-alikes.

**Today:** a customer field of kind "customer" (a doctor's hospital), built
2026-10-03; it becomes an association with the label "Works at".

## P14. The record page in three columns · adopted · I1

**From:** HubSpot's record page.

**For us:** left, who it is: name, type, code, owner, then quick actions
(Note, Email, Call, Task, Meeting) and the details by section. Middle:
Overview (the figures that matter for its type) and Activities, with search
and filters. Right: associations, quotes, deals and materials, each with
+ Add. Same wording as today; on a phone the three stack.
