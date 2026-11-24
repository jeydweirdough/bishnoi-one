"""Explicit fictional Inventory/account evidence for tests that issue coded products."""
from modules.finance import inventory

def known_product_cost(client,who,monkeypatch):
    have={a['code']:a['id'] for a in client.get('/finance/ledger/accounts',headers=who).json()['items']}
    for code,name,kind in [('5000','Fictional goods cost','expense'),('1400','Fictional inventory','asset')]:
        if code not in have:
            r=client.post('/finance/ledger/accounts',headers=who,json={'code':code,'name':name,'type':kind})
            assert r.status_code==201,r.text
            have[code]=r.json()['id']
    r=client.put('/finance/ledger/posting',headers=who,json={'accounts':{'cogs_account_id':have['5000'],'inventory_account_id':have['1400']}})
    assert r.status_code==200,r.text
    monkeypatch.setattr(inventory,'unit_costs',lambda settings,refs:{'AMX-500':100})
