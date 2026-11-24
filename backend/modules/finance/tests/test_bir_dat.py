"""BIR .DAT draft exports (SLS, SLP, SAWT, QAP) and 1702Q filing guidance."""

from datetime import date

from .test_bir_reports import QUARTER, YEAR, paid_with_withholding
from .test_invoices import issued, ready
from .test_payables import bill, cleared, supplier
from .test_tax_api import ana, app, ben, client  # noqa: F401 (fixtures)


def test_summary_lists_export_clean_bir_dat_files(client, ana, ben):  # noqa: F811
    ready(client, ana)
    paid_with_withholding(client, ben)
    # Customer with accented characters & punctuation to verify BIR text cleaning.
    issued(client, ben, customerName="Osmeña & Sons, Inc.", customerTin="987-654-321", customerAddress="123 Ayala Ave., Makati City, Metro Manila")
    s = supplier(client, ben, name="San Miguel Corp. - Pharma", tin="555666777")
    cleared(client, ana, ben, bill(client, ben, s["id"], billDate="2026-10-15"))

    sls = client.get(f"/finance/bir/lists/sls?year={YEAR}&quarter={QUARTER}&format=dat", headers=ben)
    assert sls.status_code == 200
    assert "attachment;" in sls.headers["content-disposition"] and sls.headers["content-disposition"].endswith('.DAT"')
    sls_lines = sls.text.strip().split("\r\n")
    assert sls_lines[0].startswith('H,S,"123456789"')
    assert any('"OSMENA AND SONS INC"' in ln for ln in sls_lines[1:])

    slp = client.get("/finance/bir/lists/slp?year=2026&quarter=4&format=dat", headers=ana)
    assert slp.status_code == 200
    assert slp.text.startswith('H,P,"123456789"') and '"555666777"' in slp.text

    sawt = client.get(f"/finance/bir/lists/sawt?year={YEAR}&quarter={QUARTER}&format=dat", headers=ben)
    assert sawt.status_code == 200
    assert "HSAWT,H1702Q," in sawt.text and "DSAWT,D1702Q," in sawt.text and "CSAWT,C1702Q," in sawt.text

    qap = client.get("/finance/bir/lists/qap?year=2026&quarter=4&format=dat", headers=ana)
    assert qap.status_code == 200
    assert "H1601EQ," in qap.text and "D1601EQ," in qap.text and "C1601EQ," in qap.text


def test_1702q_filing_guidance_is_available(client, ben):  # noqa: F811
    g = client.get("/finance/bir/filing-guidance?form=1702Q", headers=ben)
    assert g.status_code == 200
    assert g.json()["form"] == "1702Q" and g.json()["readyForFiling"] is False
