# Bishnoi One Finance: a guide for the finance team

This guide explains what Finance does today, step by step, in the words
the screens use. It is for the people who will use it, not for developers.

**Updated 26 October 2026 for local 0.4.16.** Open the screens at
http://localhost:4301/finance. They are part of Bishnoi One, not a separate
Finance website. For a lesson-by-lesson explanation, use the
[offline learning guide](../docs/finance-learning-guide.html).

What Finance covers today:

- **Marketing requests (cash advances):** releasing money to employees, checking
  their liquidations receipt by receipt, and settling refunds and
  reimbursements.
- **Sales invoices:** BIR-numbered invoices, customer payments, and what each
  customer owes and how late.
- **Accounting:** a chart of accounts and a journal. Every fund step records
  its own journal entry, so the books stay up to date by themselves.
- **Tax:** the company's BIR registration and the Philippine VAT rules, used to
  work out what a Sales Invoice shows.

What is **not** in Finance yet is listed at the end.

---

## 1. Signing in, and who can do what

Everyone who uses Finance has a **role**. Finance starts with three:

| | Auditor | Finance Staff | Administrator |
|---|---|---|---|
| View core records/reports and download spreadsheets allowed by the role (Calendar and Sales DAT access are separate) | ✓ | ✓ | ✓ |
| Release or decline a cash advance | | ✓ | ✓ |
| Review liquidations, record refunds and reimbursements | | ✓ | ✓ |
| Post a manual journal entry, or reverse an entry (both wait for approval) | | ✓ | ✓ |
| Approve or reject journal entries (not their own) | | | ✓ |
| Make and issue sales invoices, record their payments | | ✓ | ✓ |
| Void an invoice, set up invoice numbers | | | ✓ |
| Add, edit and switch off suppliers; make supplier bills, attach their invoices, submit them | | ✓ | ✓ |
| Prepare a payment voucher | | ✓ | ✓ |
| Approve supplier bills, check their tax withheld, release payment vouchers, void bills and vouchers | | | ✓ |
| Add or change accounts (or import a chart), default accounts and expense categories | | | ✓ |
| Change the company's tax registration, or add a new tax rate | | | ✓ |
| Add people, make roles, read the activity log | Activity log only | | ✓ |

Roles and permissions in the one app lead to the Platform's central access
screens. Our existing local Finance roles remain until the separate central-role
adoption step is approved. With Bishnoi One sign-in, changing a role only in
Finance's Users page does not reliably override the role supplied at sign-in.
Check with the administrator before changing access; do not infer a person's
permissions only from their job title.

If you sign in with your **Bishnoi One account**, your role comes from it: an
administrator of Finance there is an Administrator here; a role with the same
name as one of Finance's roles is that role; anyone else is Finance Staff.

A **red mark** in the sidebar tells Administrators that something still needs
setting up (a default account, an expense category's account, invoice numbers,
or the tax registration). Until it's set, the step that needs it can't be done.

---

## 2. The Overview page

**Payables (A+B)** now appears when you may view bills or vouchers, alongside
the existing Overview. It shows eligible approvals/checks, team draft bills,
your returned/submitted work, payment preparation/release, missing documents
and due amounts. Each count opens its matching list. Groups can contain the
same bill: do not add their amounts together. Unreleased vouchers reserve money
but do not reduce what is owed. Current supplier aging is linked from this section.

**What you see depends on your role.** A role made for your work shows the
sections that work calls for, and nothing else:

- **Waiting for you:** cash advances to release, journal entries to approve
  (not your own), prices and quotes waiting for
  your approval (asked of the CRM; it fills in a moment after the page opens,
  and says so if the CRM can't be reached), liquidations to review (not ones
  you released), refunds and reimbursements to settle, and overdue
  liquidations. Each shows only if your role does that step: for example, the
  Finance Head reviews liquidations, and the Finance Deputy releases and settles.
- **Receivables:** what customers owe, how late, and the most overdue.
- **Sales invoiced in the Hub:** this month and this year.
- **Marketing spending by team:** accepted receipts from reviewed liquidations.
- **Journal:** the latest entries and who posted them, whether the books
  balance, and how many of your own entries are still waiting for approval.
- **Tax and setup:** output tax on this quarter's invoices, and anything not yet
  set up, with a link to fix it.
- **Balances** (below).

Sales, receivables and output tax count **only invoices issued in the Hub**.
2MG's official invoices are still printed from Oojeema, so those figures stay
low until the Hub issues them.

The **Administrator, Finance Staff and Auditor** roles keep the page as it was:
what is waiting on Finance today:

- **For release:** approved requests waiting for the money to go out.
- **For review:** liquidations sent in and waiting to be checked.
- **For settlement:** refunds due from employees and reimbursements due to them.
- **Overdue liquidations:** money released whose receipts are past their due date.

Below that are today's balances of your cash and bank accounts, of **Advances to
employees** (money out and not yet accounted for), and of **Due to employees**
(reimbursements the company still owes).

---

## 3. Marketing requests, from start to finish

### Where a request comes from

1. An employee asks for money in the **CRM** (for example, a dinner with a
   doctor's clinic).
2. Their **Team Lead approves** it in the CRM, for the full amount or less.
3. The approved request arrives in Finance under **Marketing requests → For release**.

Finance never sees a request that hasn't been approved.

### Step 1: For release

Open the request and check its details: who is asking, how much was approved and
by whom, the purpose, the customer, and the date it's needed.

- **Release cash advance:** enter the amount (the approved amount or less), how
  it's paid (**Cash, Bank transfer, E-wallet (GCash, Maya)** or **Check**), a
  reference if there is one (a voucher, check or transfer number), and when the
  receipts are due. If you leave the due date blank, it's **one week** from
  today. It can't be in the past.
- **Decline release…:** give the reason. The employee sees it in the CRM, and the
  request moves to History as cancelled.

**One cash advance at a time.** While the employee still has an earlier cash
advance to liquidate (including one returned to them for correction), their
next one can't be released. The request says which one they still owe and when
it's due. Once they send that liquidation in, the next one can go, even while
Finance is still reviewing it.

Some requests are marked **"Not subject to liquidation"**. These are settled the
moment the money is released, and no receipts come back.

The employee can also cancel their own request, but only before the money is
released.

### Step 2: Outstanding (waiting for receipts)

Released money waits here until the employee sends their liquidation from the
CRM. Anything past its due date is marked **Overdue** and listed first.

For each thing they spent money on, the employee enters the date, a description,
the expense category, the amount, and a photo or PDF of the receipt (JPG, PNG,
WebP, HEIC or PDF, up to 4 MB). If there's no receipt (a jeepney fare, say),
they must say why. Spending nothing is a liquidation too: all the money then
comes back as a refund.

### Step 3: For review

**Someone other than the person who released the money reviews it.** If you
released this cash advance, the request tells you so and doesn't offer you the
review.

Go through the expenses one by one:

- **Accept** it, or **Reject…** it with a reason. The employee sees the reason.
- Change its **category** if it was filed under the wrong one. For example, a
  taxi to a client filed as Personal can be moved to Transportation.
- Open the receipt from the link under each expense.

Then either:

- **Return for correction…**, with a note on what needs fixing. The request goes
  back to Outstanding, and the employee can correct and resubmit it.
- **Complete review**, once every expense is accepted or rejected and has a
  category.

### What a liquidation comes to

> **Released − accepted expenses in reimbursable categories = what's left**

- Expenses in a category that **isn't reimbursable** (Personal) are the
  employee's own. So are **rejected** expenses. The company doesn't pay for
  either, so they don't reduce what the employee owes back.
- If something is left, it's a **Refund due** from the employee.
- If the employee spent more than was released, it's a **Reimbursement due** to
  them.
- If it comes to exactly zero, the request is **Settled** straight away.

### Step 4: For settlement

- **Record refund:** when the employee hands back the money. Enter the amount,
  how it came back, and a reference. You can record it in parts; the request is
  settled when it's all back.
- **Record reimbursement:** when Finance pays the employee. It can also be paid
  in parts.

### Step 5: History

Settled and cancelled requests. Each request keeps its **Activity log** (every
step, who did it and when) and links to the **Journal entries** it made.

### Two worked examples

**A refund.** ₱5,000.00 is released in cash. The employee sends in a ₱3,200.00
dinner (Food, reimbursable) and a ₱500.00 personal item (Personal).
Charged to the company: ₱3,200.00. **Refund due: ₱1,800.00**, which is the
₱1,300.00 unspent plus the ₱500.00 personal item.

**A reimbursement.** ₱2,000.00 is released. The employee spends ₱2,500.00 on
Food, all accepted. **Reimbursement due: ₱500.00.**

---

## 4. Sales invoices and receivables

**Invoices** in the sidebar has three pages: **Sales invoices**, **Receivables**
and **Invoice numbers**.

### Invoice numbers (set up once, by an Administrator)

Invoice numbers come from the BIR's **Authority to Print (ATP)**. On **Invoice
numbers**, **Add a series** and enter what the ATP says: its number, the date it
was issued, the first and last number, what is printed before the number (e.g.
SI-) and how many digits. Once added, only its name can change, and it can be
switched off. Each series shows how many numbers are left. A **red mark** in
the sidebar means none are left: no invoice can be issued until a new series is
added.

### An invoice, from draft to paid

1. **New invoice.** Fill in who it's for (customer, TIN, address; for a senior
   citizen or PWD, their name and ID number), the items (description, quantity,
   unit price, discount, VAT category), the invoice date and the payment terms
   in days (30 by default; 0 for cash on delivery). If the CRM is linked,
   **Find** a customer there to copy their name, TIN and address. That box only
   searches the CRM: what's typed in it isn't saved; the invoice's customer is
   the details below it. For a **TIN**, type the digits only (9, then the branch
   code if any): the dashes go in by themselves.
   **Save as draft.** A draft can still be edited or deleted. If something
   stops it from being issued, Finance says exactly what and where, on the
   invoice and beside the field when you edit it (e.g. *"Customer's TIN: Enter
   the TIN as 9 digits…"*, *"Line 2 (VAT): Pick the product's VAT category."*).
2. **Issue the invoice.** It takes the next number from the series, and its
   amounts and VAT are fixed from then on. An issued invoice is never edited:
   to correct one, cancel and reissue it (step 5).
3. **Record a payment** when the customer pays: the date, amount, how
   (Cash, Bank transfer, E-wallet or Check) and a reference (deposit slip,
   check or OR number). It can be paid in parts, but never more than is owed.
   When it's all paid, the invoice says **Paid in full**.
4. **Void** (Administrators only), with the reason. A voided invoice keeps its
   number. An invoice with payments can't be voided until they're taken off
   (**Take off**, also Administrators only).
5. **Cancel and reissue**, to correct an issued invoice (a posted invoice is
   never edited: cancel and reissue, Sir Rommel's rule). Give the reason (e.g.
   "Wrong TIN"): the invoice is voided exactly as above, and a **copy opens as a
   draft**, dated today. Correct it, change the date if needed, and **Issue**
   it: it takes the next number. Both invoices show they're linked: the new one
   says *"Replaces SI-000101, cancelled …: Wrong TIN"*, the old one *"Replaced
   by SI-000102"*, on screen, in the list and in the journal. **The printed
   invoice stays as standard**, with nothing added. An invoice voided without a
   replacement can still get one later (**Make its replacement**).

### Receivables

What each customer still owes on issued invoices, by how late it is: **Not yet
due**, **1 to 30**, **31 to 60**, **61 to 90** and **Over 90 days late**, with the
invoice numbers under each customer.

### The entries invoices make by themselves

| When | Debit | Credit |
|---|---|---|
| An invoice is issued | 1100 Accounts receivable (the total) | 4000 Sales (before VAT) and 2200 Output VAT payable (the VAT) |
| A payment is recorded | Cash / Bank / E-wallet (how it was paid) | 1100 Accounts receivable |
| An invoice is voided, or a payment taken off | The same entry reversed, dated that day | |

### Payables: suppliers and their bills

**Payables** in the sidebar has **Bills**, **Accounts payable aging**,
**Payment vouchers** and **Suppliers**.

- **Suppliers**, laid out like Zoho's vendors: the **primary contact** (salutation,
  first and last name), **company name** (as registered) and **display name** (how
  they're shown; left empty, the company name), email, work phone and mobile; then the
  **TIN** (Zoho's *Company ID*; digits only, the dashes go in by themselves), address,
  whether they're **VAT-registered**, **payment terms**, the **tax usually withheld**
  from them, picked from the BIR's codes, e.g. *WC158, goods from a company, 1%*;
  *WC160, services, 2%*; *WC100, rent, 5%*; professional fees 5–15% (the 1% and 2%
  apply when the company is a top withholding agent; Sir Rommel to confirm), and
  their own **Accounts payable** if it isn't the default (e.g. *2101-000 AP – Trade*
  or *2102-000 AP – Non-Trade*): their bills post there. Also **contact persons**,
  where they're paid, remarks, and **documents** (their BIR 2303, accreditation). The
  list shows each supplier's **Payables**: what's owed them on recorded bills. The
  same TIN and branch, or the same name, can't be added twice. A supplier is never
  deleted: **Switch off** stops them being offered on new bills.
- **Importing suppliers (Payables → Suppliers → Import from a file):** export the
  vendors from Zoho as CSV (All Vendors → ⋯ → Export) and pick the file. It's read on
  your computer and not kept. Each vendor is shown first: **New** (ticked), **Already
  here** (same name, or same TIN; left as it is) or **Needs a look** (no name, or the
  same vendor twice in the file). Zoho's *Company ID* becomes the TIN when it is one
  (otherwise it's kept in the remarks); *Net 30* becomes 30 days; inactive vendors come
  in switched off. **Import** adds the ticked ones all or none. **Not brought in:**
  what's owed them (an opening balance, to decide separately), their VAT status and
  the tax usually withheld: they come in as VAT-registered with nothing withheld, so
  set those on each supplier.
- **New bill:** pick the **supplier** (their terms, VAT and usual withholding fill
  in), type **their invoice number**, the bill date (the due date follows from the
  terms), the **PO** and **delivery receipt** numbers, and tick **checked against
  the PO / delivery receipt**. Each line: the **account** (an expense or asset), a
  description, **purchase type** (services, capital goods, other goods or importation),
  the **amount**, its **VAT** (12%, zero-rated, exempt, none) and the
  **tax withheld**. Say whether the amounts **include VAT** (as printed on the
  invoice). The bill's **Zoho** and **Oojeema** numbers can be kept on it too.
  **Save as draft.**
  *Example:* ₱11,200 for goods, VAT included, 1% withheld: ₱10,000 + ₱1,200 VAT;
  ₱100 withheld (for the supplier's 2307); **₱11,100 to pay the supplier**.
- **Attach the supplier's invoice** on the bill's page: a photo or PDF, up to 3 MB
  (photos are made smaller first). A bill without one says **Document missing**;
  **Bills → Document missing** lists them. Files can be added at any step before void.
- **Approval** (Ms. Aubrey's flow, 23 October 2026), shown on the bill's page as a
  path with who did each step:
  1. **Submit for approval** (whoever made it: Ms. Aubrey).
  2. **Approve** (Ms. Malou is told first; Ms. Cristal approves as backup; not whoever
     submitted it), or **Return for correction** with the reason.
  3. **Only if tax is withheld:** **Tax withheld checked** (Mr. Mel checks each line's
     code and rate; not whoever approved it), or return it. A bill with nothing
     withheld skips this step.
  4. **Posted to the books** when it clears, and **ready to pay**: Ms. Cristal is told.
  - While it waits it is **not in the books** and **not owed** to the supplier yet,
    and it can't be changed. **Returned**, it goes back to whoever submitted it (their
    **Returned** tab and the bell); corrected, **Submit again** sends it to approval
    from the start. Every step stays in the bill's **History**.
  - **Bills** has a tab for each step: Drafts · Returned · To approve · To check ·
    Ready to pay · Partly paid · Paid · Void · Document missing.
- **Posted, it's never changed:** **Void** it (with the reason) and enter it again.
  The same invoice number from the same supplier can't be entered twice (unless the
  first was voided).
- **Who:** each step is its own tick on the Roles screen, so any role can have
  exactly what it needs (e.g. Ms. Cristal's as well as Ms. Aubrey's). **Supplier
  bills:** View · Make drafts (make, edit, attach, submit) · Approve or return · Told
  first about bills to approve · Check the tax withheld · Void. **Suppliers:** View ·
  Add · Edit (including their documents) · Switch off.
- **Paying bills: Payables → Payment vouchers.**
  1. **Prepare** (*New payment voucher*, or *Pay this bill* on a bill ready to pay):
     pick the supplier, tick the bills it pays (only bills **ready to pay**: approved,
     and checked where tax is withheld) and how much of each (part of a bill is fine),
     how it's paid (bank transfer, check or cash) and the account it's **paid from**
     (the accounts under *CASH* in the chart: the banks, petty cash funds, GCash).
     Add the same payment's **Oojeema PV number** and **Zoho reference**. Every bill
     shows its total, what's paid, what other vouchers hold, *Pay now* and *Left
     after*. **Save and submit for release.** No other OK in the Hub: the bills were
     approved before they could be paid.
  2. **Release** (Ms. Cristal, who may also have prepared it): the date paid and the bank's reference, or the check's
     number and date. It's **posted**: what's owed the supplier down, the bank or cash
     down. The bills show **Partly paid** or **Paid**. Ma'am Mira's approval stays in
     the bank's own system (a note on release can say so).
  - **Returned** (by someone else who may release it): it goes back to whoever
    prepared it, with the reason (their **Returned** tab and the bell); they correct it
    and **Submit again**. Every step stays in the voucher's **History**.
  - **Cancel** a voucher before release (nothing was posted). **Void** a released one
    (Ms. Malou only): the entry is reversed and the bills are owed again. A bill a
    voucher pays can't be voided until the voucher is cancelled or voided.
  - **Never paid twice:** what an open voucher holds of a bill is set aside, and the
    next voucher can only take what's left.
  - **Voucher** (the button on its page) prints it: the bills paid and who approved
    each (and checked its tax withheld), the amount in words, the e-signatures
    (Prepared, Released) and a **Received by** line for the supplier. Attach the deposit slip or check photo under
    **Proof of payment**.
  - **Ticks:** Payment vouchers: View · Prepare · Release · Void.
- **Accounts payable aging:** today's unpaid/part-paid posted bills, grouped by
  supplier and due-date bucket, with owed/reserved/available amounts, bill links
  and CSV. It does not reconstruct past-date balances.
- **Supplier 2307s and purchase/withholding reports:** under **BIR reports**,
  for the roles permitted to view them. They read eligible supplier bills; no
  second purchase entry is needed when a voucher pays the bill.

| When | Debit | Credit |
|---|---|---|
| A payment voucher is released | Each bill's Accounts payable (what this voucher pays of it) | The account it's paid from |
| A payment voucher is voided | The same entry reversed, dated that day | |

| When | Debit | Credit |
|---|---|---|
| A bill clears approval (posted) | Each line's account (before VAT) and 1300 Input VAT | 2000 Accounts payable (what's paid the supplier) and 2300 Withholding tax payable – expanded |
| A bill is voided | The same entry reversed, dated that day | |

---

## 5. Accounting

### The entries marketing requests make by themselves

| When | Debit | Credit |
|---|---|---|
| Money is released | Advances to employees | Cash / Bank / E-wallet (how it was paid) |
| A review is completed | Each category's expense account (accepted, reimbursable expenses only) | Advances to employees, up to what was released; anything over goes to Due to employees |
| A refund comes back | Cash / Bank / E-wallet | Advances to employees |
| A reimbursement is paid | Due to employees | Cash / Bank / E-wallet |

Once a request is settled, its Advances to employees balance is back to zero.
Each step and its entry go through together: if an entry can't be made (a
default account isn't set, say), the step doesn't happen either.

### The starting chart of accounts

Administrators can add accounts, rename them, or switch them off. An account that already
has entries keeps its type.

| Code | Account | Type |
|---|---|---|
| 1000 | Cash on hand | Asset |
| 1010 | Cash in bank | Asset |
| 1020 | E-wallet (GCash, Maya) | Asset |
| 1100 | Accounts receivable | Asset |
| 1200 | Advances to employees | Asset |
| 1300 | Input VAT | Asset |
| 2000 | Accounts payable | Liability |
| 2100 | Due to employees | Liability |
| 2200 | Output VAT payable | Liability |
| 2300 | Withholding tax payable – expanded | Liability |
| 3000 | Owner's equity | Equity |
| 4000 | Sales | Income |
| 6100 | Food | Expense |
| 6200 | Transportation | Expense |
| 6300 | Fuel, parking & tolls | Expense |
| 6400 | Lodging | Expense |
| 6500 | Supplies & materials | Expense |
| 6900 | Other expenses | Expense |

**Importing a chart (Accounting → Chart of accounts → Import from a file):** pick
the chart as a **CSV**: Oojeema's export (Code, Name, Class, Nature, Parent, FS
Presentation) or Zoho's (Account Code, Account Name, Account Type, Parent Account).
The file is read on your computer and not kept. Every row is shown first:
**New** (ticked), **Already here** (same code; left as it is) or **Needs a look**
(no code, a code twice, a name too long, or a class Finance can't place: pick its
type on the row). The type comes from the class (e.g. *Current Liabilities* →
Liability, *Other Income* → Income). Accounts go **under their parent** by name.
**Import** adds the ticked rows **all or none**; nothing already here changes. After
importing Oojeema's chart, point the **Default accounts** at its accounts (e.g.
Input VAT 1600-000, W/tax Payable – Expanded 2302-000, Accounts Payable – Trade
2101-000). Accounts can also be put under a parent by hand (**Sits under**).

### Default accounts (Accounting → Default accounts)

These are the accounts the automatic entries use. At the start: Advances 1200,
Due to employees 2100, Cash 1000, Bank transfer 1010, E-wallet 1020, and Check
1010 (checks go through the bank account); for invoices, Receivables 1100, Sales
4000 and Output VAT 2200; for supplier bills, Accounts payable 2000, Input VAT 1300
and Withholding tax payable 2300.

### Expense categories (Accounting → Expense categories)

This is what employees file their spending under. Each category records to one
expense account, and it is either reimbursable or not. Sub-categories give more
detail and follow their category's account and rule.

| Category | Records to | Reimbursable | Sub-categories |
|---|---|---|---|
| Food | 6100 | Yes | Dining, Breakfast, Snacks & coffee |
| Transportation | 6200 | Yes | Taxi & ride-hailing, Fares, Airfare |
| Fuel, parking & tolls | 6300 | Yes | Fuel, Parking, Tolls |
| Lodging | 6400 | Yes | — |
| Supplies & materials | 6500 | Yes | Samples, Printing |
| Personal | 6900 | **No** | — |

### Journal entries (Accounting → Journal entries)

- Every entry has a number by month (JE-202609-0001), a date, a memo and its
  lines.
- **Manual journal:** debits must equal credits. Each line is either a debit or
  a credit. The date can't be in the future, and only active accounts can be
  used.
- **Entries are never edited or deleted.** To fix a mistake, **reverse**
  the entry (a new entry with the sides swapped), then post the correct one.
- **An entry typed by hand waits for approval.** A manual journal, or a
  reversal, shows **Waiting for approval** and doesn't count anywhere (balances,
  the trial balance, account ledgers, the Overview) until someone whose role may
  **Approve journal entries** approves it. Nobody approves their own entry: the
  Finance Head's entries go to the Finance Deputy. *For example, Sir Rommel posts
  ₱12,000.00 of depreciation; Ms. Malou or Ms. Cristal sees it under the bell
  and on the Overview, and once one of them approves it, it counts.*
  - **Reject** needs a reason. A rejected entry stays in the journal, marked,
    and never counts; whoever posted it is told why, and posts a corrected one.
  - If two people decide the same entry at nearly the same moment, the first
    decision stands and the second person is told who decided and when. Nothing
    else changes.
  - Entries a marketing request or an invoice makes count at once: those steps
    are approved where they happen.
  - **Approve several at once:** when two or more are yours to approve, tick
    them (or **Select all shown**) and choose **Approve selected**. Any that
    someone else had just decided, or that are your own, are named and left as
    they are. Rejecting is one at a time, each with its reason.
  - An entry whose reversal still waits shows **Reversal waiting for approval**;
    until the reversal is approved, the entry still counts.
- Filter by **All / Waiting for approval / Manual journals / Marketing requests /
  Invoices / Rejected**, pick a **From / To** date, or **Search** by entry
  number, memo or reference. The page shows the newest 200 entries; the
  download has all of them, with each one's status.

### Notifications (the bell)

The bell at the top right shows what's waiting on you, or was done to your
work. Click one to open what it's about. It's kept short:

- **The red number counts only what needs you** (something to approve, release,
  review or settle, or an entry of yours sent back). News such as "your entry
  was approved" is listed but not counted.
- **Several of a kind show as one line**, e.g. "4 journal entries are waiting
  for your approval", linking to the list.
- **Once someone acts, it leaves everyone's bell.** If Ms. Malou approves an
  entry, nobody else is still asked about it.

They go to whoever does the next step, by what their role may do, and never to
the person who did it:

| When | Who is told |
|---|---|
| A journal entry is waiting | the role ticked **Told first about entries waiting** (the Finance Head). The other approvers (the Finance Deputy) are told of the Head's own entries, and of any still waiting **one working day** later. If no role has the tick, every approver is told at once |
| An entry is approved or rejected | whoever posted it |
| A marketing request arrives for release | everyone who may release |
| A liquidation is sent in | everyone who may review, except who released it |
| A liquidation is reviewed and a refund or reimbursement is due | everyone who may settle |

**Working days** are Monday to Saturday. Philippine regular holidays and special
non-working days are days off; special working days (e.g. the EDSA anniversary)
are worked. Finance knows the holidays from the government's proclamations,
without going online, and they're updated once a year. *For example, an entry
posted Thursday 11 June 2026 reaches the Deputy on Saturday the 13th if it's still
waiting: the 12th is Independence Day.*

### E-signatures, and documents to print

**Your e-signature** is set on your account page (your name at the top right →
Your profile → **Your e-signature**). Only you can set it.

- **Draw it** in the box with a mouse, finger or pen, or **upload** a photo or
  scan. A photo of a signature on plain white paper is cleaned on your own
  computer: the paper is made transparent and the ink black, even where a
  shadow falls. Move the **Keep more / Cleaner** slider until it looks right. A
  picture that's already transparent is only trimmed. The photo itself is never
  sent.
- You confirm it's you with your **password** (or, if you sign in with your
  Bishnoi One account, by having signed in within the last 15 minutes).
- Finance places it **only by your own step**: on a journal entry you post
  (Prepared by) or approve (Approved by), and on a liquidation you review
  (Reviewed by) or settle (Settled by). Each comes with your name, role, date and
  time, "Signed electronically" and a reference to exactly what you signed.
- **Changing or removing it** doesn't change documents you already signed. An
  Administrator can remove someone's signature (e.g. when they leave), but never
  set or change it.

**Documents to print or save as PDF** (Print, then "Save as PDF"):

- **Journal voucher**: the **Voucher** link on any journal entry. Prepared by /
  Approved by. An entry made automatically by a marketing request or an invoice
  says so; its signatures are on that document.
- **Liquidation report**: the **Liquidation report** button on a marketing
  request once its liquidation is reviewed. The receipts, what they came to, and
  Reviewed by / Settled by.

*Whether BIR and the external auditors accept e-signed documents is being
confirmed with Sir Rommel; meanwhile everyone, Sir Rommel included, can sign.*

### Calendar

**Calendar** in the sidebar is for your deadlines, cut-offs and monthly tasks:
BIR filings, ER cut-offs, the bank reconciliation, card statements. It's
**switched on per person** by an Administrator (Administration → Users,
**Calendar on/off**), not given with a role.

- **Add an event:** what, the date (and a time if you like), whether it repeats
  (every month, every 3 months, every year, or twice a month on the 15th and the
  last day), and when to **remind** you: on the day, or 1, 3 or 7 working days
  before. You can point it to a Finance page (e.g. BIR sales DAT).
- **Your calendar is yours.** Nobody else sees your events unless you **share**
  one with them (with people who also have the calendar). They're told, they see
  it, and they can mark it done; only you can change or delete it.
- **Reminders** come in the bell and in **Coming up** on the Overview, when you
  open Finance (there's no email). *For example, an event due Monday 9 November 2026,
  set to remind 3 working days before, reminds you on Thursday the 5th
  (Saturday the 7th counts as a working day).*
- **Mark done** stops the reminder for that date, for you and everyone it's
  shared with. **Not done** undoes it.
- Shown by themselves: Philippine **holidays** and Sundays (shaded), and
  **liquidations falling due**, for whoever releases or reviews them.

### Account ledgers and the trial balance

- Click any account to see its **ledger**: every line, with the balance after
  each. Pick dates to start from a balance brought forward.
- **Trial balance:** every account's debits and credits as of a day you pick.
  The totals must be equal, and the page tells you if they aren't.

### Downloading to Excel

The Journal entries, account ledger, Trial balance and every Marketing requests list
have a **Download CSV** button. The file opens in Excel and contains what the
page shows, with the same dates, filters and search, and **every** row, not just
the first page:

- Amounts are plain numbers (1234.50, or -500.00 when negative), so Excel can
  add them up.
- Text that Excel might mistake for a formula is shown exactly as typed.
- The marketing requests file has each request's approved, released, spent, refund
  and reimbursement amounts, and its dates.

---

## 6. Tax

**Tax** in the sidebar has three tabs:

- **Registration:** the company's registered name (exactly as on the BIR
  Certificate of Registration), trade name, TIN with its branch code (00000 for
  the head office), registered address, whether the company is VAT-registered,
  and whether catalogue prices already include VAT. Administrators fill this in once
  (**Save registration**). Every Sales Invoice needs it. There's one registration
  per company, changed in place. If the registered name, TIN or registered
  address is still empty, the top of the page names which one, its box is
  marked, and saving says "Still missing: …". Invoices can't be issued until
  all three are filled in, and a draft invoice says the same, with a link here.
  At the top, **On record** shows the registration as it stands and who changed
  it last; below the form, **History** lists each change (who, when, and which
  parts, never the old values). Everyone who can see Tax sees both; only those
  who can change it see the form.
- **Rates:** each tax's rate by date. A change in the law is entered as a new
  rate from its first day, with the law or circular behind it. A sale is always
  taxed at the rate of its own day.
- **Try a sale:** enter lines and a buyer to see the **Sales Invoice summary**:
  VATable sales, VAT, zero-rated sales and VAT-exempt sales.

The Philippine rules built in:

- VAT is 12%. Zero-rated sales are 0%. VAT-exempt sales carry no VAT. Whether a
  product is zero-rated or exempt is set per product.
- Senior citizens and persons with disability buying covered goods, such as
  medicines, get **20% off the price without VAT, and no VAT**. For example,
  ₱112.00 with VAT becomes ₱100.00 without it, less ₱20.00, so ₱80.00 is due.
  Their name and OSCA or PWD ID number go on the invoice.
- A company that isn't VAT-registered charges no VAT and pays percentage tax on
  its sales (3%).

> **Please have your accountant confirm these rules** before relying on them
> for filing. They are written down as the law is understood in 2026; they are
> not tax advice.

The CRM can use these rules to add tax to its quotes, once the two apps are
connected.

### BIR sales DAT (Sir Rommel's role only)

**BIR sales DAT** in the sidebar makes the monthly Summary List of Sales file
(the `.DAT` sent to BIR through RELIEF) from Oojeema's exports. It does what the
converter page Sir Rommel used before, with the same results, and it opens only
for a role allowed to **Prepare BIR files**. Role management in the one app
links to the Platform's access screens; existing local Finance roles remain
until the separate central-role adoption step.

- **Prepare monthly DAT:** drop the month's exports from Oojeema (the DAT, the
  Sales Relief or Sales Journal, the General Ledger, the Income Statement). Pick
  the month. Finance applies the rules Sir Rommel confirmed (listed on the page
  under **Rules in use**), explains any difference from the Income Statement,
  and gives the corrected DAT, a CSV and an Excel report to download.
- **Convert as-is:** Oojeema's Sales Relief CSV into a DAT, with no corrections.
- **DAT to CSV:** a DAT back into a spreadsheet, for example to check one already filed.

Nothing is uploaded: the files are read on your own computer.

The first line of every DAT names the company's **RDO** (the BIR district office
it is registered with, a code like `53A`) and the **month its year ends**
(`12` for a year ending in December). Both are printed on the company's BIR
Certificate of Registration (Form 2303). For 2MG, Finance uses **53A and
December**, as in the DATs filed for March to September 2026; please check them
against 2MG's certificate. Getmeds Philippines has none set yet, so the page asks
for them before it gives a file.

Before filing, run each DAT through BIR's RELIEF Validation Module, as before.

---

## 7. Not in Finance yet

- **Quote approvals, guarantee letter checks and letter payments** (DSWD, PCSO,
  and others) are done in the **CRM** today, by each team's **Team Lead**, not by
  Finance.
- **Opening balances and linked historical transaction imports:** the supplier
  and chart importers do not bring in bills, payments, sales or account balances.
  The cut-off/history strategy is still to be agreed.
- **Credit memos/sales returns, the full importation workflow, and complete
  purchase-tax detail for non-bill spending** remain to be planned and built.
- **Official sales ingestion, remaining BIR submission formats and production
  rollout** still require decisions and validation. GPI stays on Zoho under the
  recorded scope; this is not a completed two-company accounting rollout.
- **Already available:** current supplier aging, supplier 2307 report views,
  financial statements and bank reconciliation. Validate their results with
  Finance before relying on them for filing.

---

## 8. Tell us if this doesn't match how you work

Some choices are built in today but can change. Please tell us:

1. **Accounts and categories.** Do the starting accounts, codes and expense
   categories above match your own chart of accounts?
2. **Anything you do outside Bishnoi One today** (spreadsheets, forms, reports) that
   you would like it to do instead.

Already answered in the October questionnaire: releasing and reviewing are done
by different people; receipts are due in one week, and an employee liquidates
before the next release; entries a marketing request made can still be reversed
from the journal.

## Printing and Save as PDF (local 0.4.16)
Finance record/report print views use a common company/system header and footer. For the signed-in2MG company this includes the supplied2MG logo and smaller Bishnoi One mark. Invoice registration fields, document numbers/statuses, tables, totals and recorded signatures remain part of the source document. Wide schedules request landscape; ordinary documents request portrait.
Use Print / Save as PDF on report/record views, or the existing document Print button. Images/fonts are awaited; a failed logo/signature prompts a refresh instead of knowingly printing incomplete evidence. Applied filter context is printed; unsent filter edits are not treated as report filters. Check preview before saving; browser settings can override size/orientation. Browser visual/pagination acceptance is still pending, not implied by server-render checks. CSV/DAT unchanged.

### Printing attached documents (0.4.17)
Use Print / Save as PDF to append attached PDF pages and photos to bills, supplier records and vouchers. Existing file permissions apply. Printing stops if files cannot be prepared; original downloads remain unchanged. Packets above100 supporting pages must be printed separately. Browser-menu printing warns if attachments are unprepared. Actual browser preview acceptance pending.

### Supplier import review (0.4.18)
Use Suppliers -> Import from a file. The existing inline panel/table recognises CF.TIN and CF.Contact Number. Expand column coverage and each row's details to inspect what will be saved. Explicitly confirm VAT/withholding; confirm payable mappings and conflicting terms/addresses. Invalid TINs block the row; missing TINs require acknowledgement and remain incomplete for BIR details. Additional numbers and labelled terms/billing details use existing fields,with visible overflow errors. Filters preserve selections; group tax choices require explicit confirmation. After editing,Recheck preview retains deliberate exclusions and selects newly ready rows. Final confirmation imports selected suppliers all or none after backend validation. Existing suppliers remain unchanged;source IDs,bills,payments and opening balances are excluded. Unknown outcomes require rechecking before retry. Decisions are temporary until import; closing/picking another file warns that choices will be lost.

### Directory-first import0.4.19 (supersedes0.4.18 review instructions)
Choose CSV -> optional summary/details -> one Import directory confirmation. No individual vendor reviews. Clear directory facts imported automatically; duplicates/existing/unusable/conflicting identities excluded. Unresolved values/hints retained under Imported details kept for later. Tax defaults unconfirmed;actual bill VAT/withholding must be explicitly chosen and reviewed before submission. Edit suppliers permission allows optional saved defaults from bill or supplier form. Existing values/posted bills preserved;source IDs/bills/payments/opening balances not imported. Recheck before retry after an unknown outcome.
