"""Settings -> Company: the record every screen reads its money and dates from."""


def test_an_admin_changes_what_this_company_is(client, as_):
    carmen = as_("carmen")
    before = client.get("/admin/company", headers=carmen).json()
    assert (before["currency"], before["minorUnits"], before["timezone"]) == ("PHP", 2, "Asia/Manila")
    assert before["example"] == "₱1,234.56"

    r = client.patch(
        "/admin/company",
        json={"name": "Getmeds Global", "currency": "usd", "minorUnits": 2, "timezone": "Europe/London", "locale": "en-GB"},
        headers=carmen,
    )
    assert r.status_code == 200, r.text
    assert r.json()["currency"] == "USD" and r.json()["example"] == "$1,234.56"

    # and every screen is told at once, through the sign-in payload
    org = client.get("/auth/me", headers=as_("lorna")).json()["org"]
    assert (org["currency"], org["timezone"], org["locale"], org["name"]) == ("USD", "Europe/London", "en-GB", "Getmeds Global")


def test_a_currency_with_no_decimals(client, as_):
    carmen = as_("carmen")
    r = client.patch("/admin/company", json={"currency": "JPY", "minorUnits": 0}, headers=carmen)
    assert r.json()["example"] == "¥123,456"


def test_nonsense_is_refused_with_the_field_named(client, as_):
    carmen = as_("carmen")
    bad_zone = client.patch("/admin/company", json={"timezone": "Middle/Earth"}, headers=carmen)
    assert bad_zone.status_code == 422 and "time zone" in str(bad_zone.json()["detail"])
    assert client.patch("/admin/company", json={"currency": "12£"}, headers=carmen).status_code == 422
    assert client.patch("/admin/company", json={"minorUnits": 9}, headers=carmen).status_code == 422
    # the company is untouched by any of that
    assert client.get("/admin/company", headers=carmen).json()["currency"] == "PHP"


def test_only_an_admin_may_change_it(client, as_):
    assert client.get("/admin/company", headers=as_("lorna")).status_code == 403
    assert client.patch("/admin/company", json={"name": "Mine now"}, headers=as_("lorna")).status_code == 403
