"""Step 3 BIR fixes: calendar-quarter enforcement on withholding returns and CSV exports for statements."""
from modules.finance.models import TaxProfile
from .test_tax_api import app, client, ana


def test_withholding_uses_calendar_quarters_even_when_fiscal_differs(app, client, ana):
    with app.state.sessions() as db:
        tp = db.get(TaxProfile, 1)
        if tp is None:
            tp = TaxProfile(id=1, registered_name="Test Corp", fiscal_month_end=6)
            db.add(tp)
        else:
            tp.fiscal_month_end = 6
        db.commit()

    for path in (
        "/finance/bir/withholding/1601eq?year=2026&quarter=1",
        "/finance/bir/withholding/2307?year=2026&quarter=1",
        "/finance/bir/lists/qap?year=2026&quarter=1",
        "/finance/bir/lists/sawt?year=2026&quarter=1",
    ):
        res = client.get(path, headers=ana)
        assert res.status_code == 200, res.text
        period = res.json()["period"]
        assert period["start"] == "2026-01-01"
        assert period["end"] == "2026-03-31"

    res_annual = client.get("/finance/bir/withholding/1604e?year=2026", headers=ana)
    assert res_annual.status_code == 200, res_annual.text
    assert res_annual.json()["period"]["start"] == "2026-01-01"
    assert res_annual.json()["period"]["end"] == "2026-12-31"


def test_income_statement_and_balance_sheet_csv_exports(app, client, ana):
    inc = client.get("/finance/bir/statements/income?start=2026-01-01&end=2026-03-31&format=csv", headers=ana)
    assert inc.status_code == 200, inc.text
    assert "text/csv" in inc.headers["content-type"]
    assert "Section,Code,Account,Amount" in inc.text
    assert "Total income" in inc.text

    bs = client.get("/finance/bir/statements/balance?asOf=2026-03-31&format=csv", headers=ana)
    assert bs.status_code == 200, bs.text
    assert "text/csv" in bs.headers["content-type"]
    assert "Section,Code,Account,Amount" in bs.text
    assert "Total liabilities and equity" in bs.text
