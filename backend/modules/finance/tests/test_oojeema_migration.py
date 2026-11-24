"""Synthetic tests for Oojeema Smart COA recovery, Real/Nominal exceptions, Dec 31 opening, and Q1 GL posting."""
from datetime import date

from sqlalchemy import select

from modules.finance import bir_reports
from modules.finance.models import Account
from modules.finance.oojeema_migration import post_gl_q1_movements
from .test_tax_api import app, client, ana


ACTIVE_COA_CSV = """Code,Name,Class,Nature,Type,Parent,FS Presentation
0006,Cash in Bank - Test,Cash,Debit,Child,CASH,Balance Sheet
001,Suspense Other Expense,Other Expenses,Debit,Child,,Income Statement
4000-000,Revenue Header,Revenue,Credit,Parent,,Income Statement
6814-000,Accumulated Depreciation - PPE,Fixed Assets,Credit,Child,,Balance Sheet
"""

INACTIVE_COA_CSV = """Code,Name,Class,Nature,Type,Parent,FS Presentation
6226-000,Old Travel Expense,Operating Expenses,Debit,Child,,Income Statement
"""

DEC_TB_CSV = """TAXPAYER TRADE NAME,SAMPLE CORP
Trial Balance
Date :,Dec 01 2025 - Dec 31 2025
Account Code,Account Name,Prev Carryforward,Balance Carryforward,Total Debit,Total Credit,Balance for the Period,Accumulated Balance
0006,Cash in Bank - Test,1000.00,0.00,500.00,0.00,500.00,1500.00
2101-000,Accounts Payable - Trade,(200.00),0.00,0.00,300.00,(300.00),(500.00)
3103-000,Income Summary,0.00,0.00,0.00,0.00,0.00,0.00
4100-000,Sale of Goods,0.00,0.00,0.00,2000.00,(2000.00),(2000.00)
6226-000,Old Travel Expense,0.00,0.00,1000.00,0.00,1000.00,1000.00
Totals:,Totals,800.00,0.00,1500.00,2300.00,(800.00),0.00
"""

Q1_GL_CSV = """TAXPAYER TRADE NAME,SAMPLE CORP
General Ledger
Account Name
Transaction Date,Customer / Vendor,Description,Status,Check Number,Reference Number,Voucher Number,Total Debit,Total Credit
Cash in Bank - Test(0006)
Beginning Balance,,,,,,,1500.00,0.00
"Jan 15, 2026",Test Customer,Collection,open,,,JV-100,500.00,0.00
Old Travel Expense(6226-000)
"Jan 15, 2026",Test Vendor,Prior travel,open,,,JV-100,0.00,500.00
"""


def test_oojeema_coa_opening_and_q1_gl_tieout(app, client, ana):
    res = client.post(
        "/finance/ledger/opening/oojeema",
        headers=ana,
        json={
            "activeCoaCsv": ACTIVE_COA_CSV,
            "inactiveCoaCsv": INACTIVE_COA_CSV,
            "decTbCsv": DEC_TB_CSV,
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    # 3 TB-only accounts recovered: 2101-000, 3103-000, 4100-000
    assert set(body["recoveredCodes"]) == {"2101-000", "3103-000", "4100-000"}
    assert body["deactivated"] == 1
    exception_codes = {e["code"] for e in body["realNominalExceptions"]}
    assert exception_codes == {"001", "4000-000", "6814-000"}

    # Inactive account 6226-000 is switched off after opening, while Real balances carry into Jan 1
    with app.state.sessions() as db:
        old_exp = db.scalar(select(Account).where(Account.code == "6226-000"))
        assert old_exp is not None and old_exp.is_active is False

        bs = bir_reports.balance_sheet(db, date(2025, 12, 31))
        assert bs["totals"]["balanced"] is True

        # 2026 Income Statement starts at 0 (2025 P&L closed into 3103-000)
        is_2026_start = bir_reports.income_statement(db, date(2026, 1, 1), date(2026, 1, 1))
        assert is_2026_start["totals"]["incomeCentavos"] == 0
        assert is_2026_start["totals"]["expensesCentavos"] == 0

        # Post Q1 GL voucher touching inactive account 6226-000 and verify it succeeds and stays inactive
        gl_res = post_gl_q1_movements(db, Q1_GL_CSV)
        db.commit()
        assert gl_res["vouchersPosted"] == 1
        assert gl_res["unbalancedVouchers"] == []
        db.refresh(old_exp)
        assert old_exp.is_active is False
