from datetime import date,timedelta
import pytest
from sqlalchemy import select
from .test_tax_api import app,ana,client,REGISTRATION
from .test_invoices import TODAY


def test_rdo_accepts_letters_roundtrips_and_rejects_bad_codes(client,ana):
    r=client.put('/tax/profile',json={**REGISTRATION,'rdoCode':'53a'},headers=ana)
    assert r.status_code==200,r.text
    assert r.json()['profile']['rdoCode']=='53A'
    assert client.get('/finance/bir/returns/vat',headers=ana).json()['taxpayer']['rdoCode']=='53A'
    from pypdf import PdfReader
    from io import BytesIO
    pdf=client.get('/finance/bir/returns/vat/draft.pdf',headers=ana)
    assert pdf.status_code==200,pdf.text if pdf.status_code!=200 else ''
    # The official form has one character per cell; extraction separates cells.
    assert '\n5\n3\nA\n' in PdfReader(BytesIO(pdf.content)).pages[0].extract_text()
    for value in ['ABC','5-A','1234','5','1!2',123]:
        assert client.put('/tax/profile',json={**REGISTRATION,'rdoCode':value},headers=ana).status_code==422
    r=client.put('/tax/profile',json={**REGISTRATION,'rdoCode':'053'},headers=ana)
    assert r.status_code==200 and r.json()['profile']['rdoCode']=='053'
