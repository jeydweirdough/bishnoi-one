# Nabhi Finance: a guide for the finance team

This guide explains what Nabhi Finance does today, step by step, in the words
the screens use. It is for the people who will use it, not for developers.

What Finance covers today:

- **Fund requests (cash advances):** releasing money to employees, checking
  their liquidations receipt by receipt, and settling refunds and
  reimbursements.
- **Accounting:** a chart of accounts and a journal. Every fund step records
  its own journal entry, so the books stay up to date by themselves.
- **Tax:** the company's BIR registration and the Philippine VAT rules, used to
  work out what a Sales Invoice shows.

What is **not** in Finance yet is listed at the end.

---

## 1. Signing in, and who can do what

Everyone who uses Finance has one of two roles:

| | Member | Admin |
|---|---|---|
| See every page, request and entry | ✓ | ✓ |
| Release or decline a cash advance | ✓ | ✓ |
| Review liquidations, record refunds and reimbursements | ✓ | ✓ |
| Post a manual journal entry, or reverse an entry | ✓ | ✓ |
| Work out a sale's tax, download spreadsheets | ✓ | ✓ |
| Add or change accounts, default accounts and expense categories | | ✓ |
| Change the company's tax registration, or add a new tax rate | | ✓ |

If you sign in with your **Nabhi account**, your role comes from it: a Nabhi
administrator (or an app admin for Finance) is an Admin here, and everyone else
is a Member.

A **red mark** in the sidebar tells Admins that something still needs setting up
(a default account, an expense category's account, or the tax registration).
Until it's set, the step that needs it can't be done.

---

## 2. The Overview page

The first page shows what is waiting on Finance today:

- **For release:** approved requests waiting for the money to go out.
- **For review:** liquidations sent in and waiting to be checked.
- **For settlement:** refunds due from employees and reimbursements due to them.
- **Overdue liquidations:** money released whose receipts are past their due date.

Below that are today's balances of your cash and bank accounts, of **Advances to
employees** (money out and not yet accounted for), and of **Due to employees**
(reimbursements the company still owes).

---

## 3. Fund requests, from start to finish

### Where a request comes from

1. An employee asks for money in the **CRM** (for example, a dinner with a
   doctor's clinic).
2. Their **Team Lead approves** it in the CRM, for the full amount or less.
3. The approved request arrives in Finance under **Fund requests → For release**.

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

## 4. Accounting

### The entries fund requests make by themselves

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

Admins can add accounts, rename them, or switch them off. An account that already
has entries keeps its type.

| Code | Account | Type |
|---|---|---|
| 1000 | Cash on hand | Asset |
| 1010 | Cash in bank | Asset |
| 1020 | E-wallet (GCash, Maya) | Asset |
| 1200 | Advances to employees | Asset |
| 2000 | Accounts payable | Liability |
| 2100 | Due to employees | Liability |
| 3000 | Owner's equity | Equity |
| 4000 | Sales | Income |
| 6100 | Food | Expense |
| 6200 | Transportation | Expense |
| 6300 | Fuel, parking & tolls | Expense |
| 6400 | Lodging | Expense |
| 6500 | Supplies & materials | Expense |
| 6900 | Other expenses | Expense |

### Default accounts (Accounting → Default accounts)

These are the accounts the automatic entries use. At the start: Advances 1200,
Due to employees 2100, Cash 1000, Bank transfer 1010, E-wallet 1020, and Check
1010 (checks go through the bank account).

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
- **Posted entries are never edited or deleted.** To fix a mistake, **reverse**
  the entry (a new entry with the sides swapped), then post the correct one.
- Filter by **All / Manual journals / Fund requests**, pick a **From / To** date,
  or **Search** by entry number, memo or reference. The page shows the newest
  200 entries; the download has all of them.

### Account ledgers and the trial balance

- Click any account to see its **ledger**: every line, with the balance after
  each. Pick dates to start from a balance brought forward.
- **Trial balance:** every account's debits and credits as of a day you pick.
  The totals must be equal, and the page tells you if they aren't.

### Downloading to Excel

The Journal entries, account ledger, Trial balance and every Fund requests list
have a **Download CSV** button. The file opens in Excel and contains what the
page shows, with the same dates, filters and search, and **every** row, not just
the first page:

- Amounts are plain numbers (1234.50, or -500.00 when negative), so Excel can
  add them up.
- Text that Excel might mistake for a formula is shown exactly as typed.
- The fund requests file has each request's approved, released, spent, refund
  and reimbursement amounts, and its dates.

---

## 5. Tax

**Tax** in the sidebar has three tabs:

- **Registration:** the company's registered name (exactly as on the BIR
  Certificate of Registration), trade name, TIN with its branch code (00000 for
  the head office), registered address, whether the company is VAT-registered,
  and whether catalogue prices already include VAT. Admins fill this in once
  (**Save registration**). Every Sales Invoice needs it.
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

---

## 6. Not in Finance yet

- **Quote approvals, guarantee letter checks and letter payments** (DSWD, PCSO,
  and others) are done in the **CRM** today, by each team's **Team Lead**, not by
  Finance.
- **Invoices, customer payments and receivables ageing:** planned as Finance's
  next step.
- **Supplier bills and payments** (accounts payable), **bank reconciliation**, and
  **separate books for 2mg Incorporated and Getmeds Philippines Inc.**: not
  started.

---

## 7. Tell us if this doesn't match how you work

Some choices are built in today but can change. Please tell us:

1. **Who may do what.** Today any Finance member can release money, review the
   same liquidation, and record the refund. Should releasing and reviewing be
   done by different people?
2. **The liquidation period.** Receipts are due one week after release unless
   you pick another date. Is one week right?
3. **Accounts and categories.** Do the starting accounts, codes and expense
   categories above match your own chart of accounts?
4. **Reversing fund entries.** Today an entry a fund request made can be
   reversed from the journal, like any other. Should those only change through
   the request itself?
5. **Anything you do outside Nabhi today** (spreadsheets, forms, reports) that
   you would like it to do instead.
