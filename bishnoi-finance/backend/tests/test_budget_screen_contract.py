"""Exercise the screen's real request against the API, including its year filter."""
from pathlib import Path
import re

from .test_tax_api import app, client, ana
from .test_banking import account


def test_budget_screen_request_uses_the_selected_year(client, ana):
    root = Path(__file__).resolve().parents[3]
    screen = (root / 'bishnoi-one-app/frontend/src/modules/finance/screens/assets.tsx').read_text(encoding='utf-8')
    request = re.search(r'`(/finance/budgets\?[^`]+)`', screen).group(1)
    expense = account(client, ana, '6980', 'Budget contract test', 'expense')
    saved = []
    for year in (2026, 2027):
        response = client.put('/finance/budgets', headers=ana, json={
            'yearEnd': f'{year}-12-31', 'accountId': expense, 'yearlyCentavos': year * 100,
        })
        assert response.status_code == 200, response.text
        saved.append(response.json()['id'])
    url = request.replace('${chosen}', '2026-12-31')
    response = client.get(url, headers=ana)
    assert response.status_code == 200, response.text
    assert response.json()['yearEnd'] == '2026-12-31'
    assert [row['id'] for row in response.json()['items']] == saved[:1]
    assert client.get(url).status_code in (401, 403)
    assert client.get(request.replace('${chosen}', 'not-a-date'), headers=ana).status_code == 422
