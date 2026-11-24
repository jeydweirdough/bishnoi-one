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


def test_monthly_dat_exports_and_split_sawt_2550q_vs_1702q(client, ana, ben):  # noqa: F811
    from .test_bir_reports import ready

    ready(client, ana)
    inv_cwt = issued(client, ben, invoiceDate=f"{YEAR}-10-01", customerName="Private Pharmacy", customerTin="111-222-333")
    inv_wv = issued(client, ben, invoiceDate=f"{YEAR}-10-02", customerName="Government Hospital", customerTin="444-555-666")
    # Record 1% WC158 on one invoice and 5% WV010 VAT withholding on the other (same quarter/month).
    assert client.post(
        f"/finance/invoices/{inv_cwt['id']}/payments",
        json={"paidOn": f"{YEAR}-10-08", "method": "cash", "amountCentavos": 222_000, "cwtCentavos": 2_000, "cwtAtc": "WC158", "cwtCertificate": "2307-1"},
        headers=ben,
    ).status_code == 201
    assert client.post(
        f"/finance/invoices/{inv_wv['id']}/payments",
        json={"paidOn": f"{YEAR}-10-12", "method": "bank", "amountCentavos": 214_000, "cwtCentavos": 10_000, "cwtAtc": "WV010", "cwtCertificate": "2307-2"},
        headers=ben,
    ).status_code == 201

    s = supplier(client, ben, name="Local Med Distributor", tin="555-666-777")
    cleared(client, ana, ben, bill(client, ben, s["id"], billDate=f"{YEAR}-10-15"))

    # Monthly .DAT files match BIR period/filename conventions.
    sls_m = client.get(f"/finance/bir/lists/sls?year={YEAR}&quarter=4&month=10&format=dat", headers=ben)
    assert sls_m.status_code == 200
    assert 'filename="123456789S102026.DAT"' in sls_m.headers["content-disposition"]
    assert ",10/31/2026," in sls_m.text

    slp_m = client.get(f"/finance/bir/lists/slp?year={YEAR}&month=10&format=dat", headers=ana)
    assert slp_m.status_code == 200
    assert 'filename="123456789P102026.DAT"' in slp_m.headers["content-disposition"]

    qap = client.get(f"/finance/bir/lists/qap?year={YEAR}&quarter=4&format=dat", headers=ana)
    assert qap.status_code == 200
    assert 'filename="12345678900001220261601EQ.DAT"' in qap.headers["content-disposition"]
    assert ",12/2026," in qap.text

    bad_m = client.get(f"/finance/bir/lists/sls?year={YEAR}&quarter=1&month=10", headers=ben)
    assert bad_m.status_code == 422

    # Split SAWT: 2550Q carries WV010 only; 1702Q carries WC158 only.
    sawt_2550 = client.get(f"/finance/bir/lists/sawt?year={YEAR}&quarter=4&month=10&form=2550Q&format=dat", headers=ben)
    assert sawt_2550.status_code == 200
    assert 'filename="12345678900001020262550Q.DAT"' in sawt_2550.headers["content-disposition"]
    assert "HSAWT,H2550Q," in sawt_2550.text and "WV010" in sawt_2550.text and "WC158" not in sawt_2550.text

    sawt_1702 = client.get(f"/finance/bir/lists/sawt?year={YEAR}&quarter=4&month=10&form=1702Q&format=dat", headers=ben)
    assert sawt_1702.status_code == 200
    assert 'filename="12345678900001020261702Q.DAT"' in sawt_1702.headers["content-disposition"]
    assert "HSAWT,H1702Q," in sawt_1702.text and "WC158" in sawt_1702.text and "WV010" not in sawt_1702.text

    # Non-zero 5-digit branch uses trailing 4 digits per BIR DAT rules.
    from modules.finance.bir_dat import branch4
    assert branch4("00001") == "0001"
