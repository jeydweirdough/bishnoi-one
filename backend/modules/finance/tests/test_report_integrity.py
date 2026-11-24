"""Report integrity regressions: fictional data only."""
from datetime import date, datetime, timezone
from types import SimpleNamespace
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
import pytest
from fastapi import HTTPException
from modules.finance.db import Base
from modules.finance.models import FundRequest, FundExpense, ExpenseCategory
from modules.finance.routers import reports, invoices
from modules.finance import inventory

def test_unchecked_liquidation_does_not_appear_as_recognized_expense():
    engine=create_engine('sqlite://');Base.metadata.create_all(engine)
    with Session(engine) as db:
        r=FundRequest(source_app='fictional',source_id='integrity-test',number='EXAMPLE',requester_name='Example reviewer',requester_email='example@example.test',purpose='Example',requested_centavos=10000,approved_centavos=10000,approved_by_name='Example approver',approved_at=datetime.now(timezone.utc),status='to_check')
        category=ExpenseCategory(name='Example category',reimbursable=True)
        db.add_all([r,category]);db.flush()
        e=FundExpense(request_id=r.id,category_id=category.id,spent_on=date(2026,11,19),description='Fictional receipt',amount_centavos=10000)
        db.add(e);db.flush();ctx=SimpleNamespace(db=db,first=date(2026,11,1),last=date(2026,11,30))
        assert reports.expenses_by_category(ctx)[1]==[]
        e.accepted=True;db.flush()
        assert reports.expenses_by_category(ctx)[1]==[]
        r.checked_at=datetime.now(timezone.utc);db.flush()
        assert sum(x['amount'] for x in reports.expenses_by_category(ctx)[1])==10000
        category.reimbursable=False;db.flush()
        assert reports.expenses_by_category(ctx)[1]==[]
        category.reimbursable=True
        e.accepted=False;db.flush()
        assert reports.expenses_by_category(ctx)[1]==[]

@pytest.mark.parametrize('costs',[None,{}, {'EXAMPLE':None},{'EXAMPLE':-1}])
def test_unknown_product_cost_refuses_instead_of_becoming_zero(monkeypatch,costs):
    monkeypatch.setattr(invoices,'posting_settings',lambda db:SimpleNamespace(cogs_account_id='example',inventory_account_id='example'))
    monkeypatch.setattr(inventory,'unit_costs',lambda settings,refs:costs)
    with pytest.raises(HTTPException) as e:invoices.cost_lines(None,None,SimpleNamespace(lines=[{'ref':'EXAMPLE','quantity':2}]))
    assert e.value.status_code==409

def test_explicit_zero_cost_is_distinct_from_missing(monkeypatch):
    monkeypatch.setattr(invoices,'posting_settings',lambda db:SimpleNamespace(cogs_account_id='example',inventory_account_id='example'))
    monkeypatch.setattr(inventory,'unit_costs',lambda settings,refs:{'EXAMPLE':0})
    assert invoices.cost_lines(None,None,SimpleNamespace(lines=[{'ref':'EXAMPLE','quantity':2}]))==([0],0)


def test_historical_forecast_keeps_invoice_owed_before_later_payment(client,ana):
    from datetime import timedelta
    from .test_invoices import ready,issued
    ready(client,ana)
    today=date.today();old=(today-timedelta(days=60)).isoformat();on=(today-timedelta(days=45)).isoformat()
    inv=issued(client,ana,invoiceDate=old)
    response=client.post(f"/finance/invoices/{inv['id']}/payments",json={'paidOn':(today-timedelta(days=30)).isoformat(),'amountCentavos':224000,'method':'cash'},headers=ana)
    assert response.status_code==201,response.text
    past=client.get('/finance/reports/cash-forecast',params={'from':on,'to':on},headers=ana)
    assert past.status_code==200,past.text
    assert sum(r['inflow'] for r in past.json()['rows'])==224000
    now=client.get('/finance/reports/cash-forecast',params={'from':today.isoformat(),'to':today.isoformat()},headers=ana)
    assert sum(r['inflow'] for r in now.json()['rows'])==0

from .test_tax_api import app,client,ana
