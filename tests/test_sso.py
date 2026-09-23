"""One sign-in for Orbit and the Orders app, and one sign-out."""

import base64
import hashlib
import secrets
from datetime import timedelta

import jwt
import pytest

from app.keys import SigningKeys, new_private_pem
from app.models import SsoClient, SsoCode, utcnow
from app.routers.sso import digest
from app.tenancy import all_companies

REDIRECT = "https://orders.example.test/sso/callback"
SECRET = "orders-client-secret-for-tests"


@pytest.fixture
def orders_app(app):
    with app.state.sessions() as db:
        db.add(SsoClient(id="orders", name="Orders", secret_hash=digest(SECRET), redirect_uris=[REDIRECT]))
        db.commit()
    return app


def pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


def code_for(client, headers, challenge, redirect=REDIRECT, client_id="orders"):
    return client.post("/sso/codes", json={"clientId": client_id, "redirectUri": redirect, "codeChallenge": challenge}, headers=headers)


def swap(client, code, verifier, secret=SECRET, redirect=REDIRECT):
    return client.post(
        "/sso/token",
        json={"grantType": "authorization_code", "code": code, "clientId": "orders", "clientSecret": secret,
              "redirectUri": redirect, "codeVerifier": verifier},
    )


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def sign_in(client, who="ana") -> dict:
    r = client.post("/auth/login", json={"email": f"{who}@pharmacrm.test", "password": "demo1234"})
    assert r.status_code == 200, r.text
    return bearer(r.json()["accessToken"])


def test_tokens_are_signed_with_a_key_anyone_can_check(client, as_):
    keys = client.get("/.well-known/jwks.json").json()["keys"]
    assert len(keys) == 1 and keys[0]["kty"] == "OKP" and keys[0]["crv"] == "Ed25519" and "d" not in keys[0]
    token = as_("ana")["Authorization"].removeprefix("Bearer ")
    header = jwt.get_unverified_header(token)
    assert header["alg"] == "EdDSA" and header["kid"] == keys[0]["kid"]
    public = jwt.PyJWK(keys[0]).key
    claims = jwt.decode(token, public, algorithms=["EdDSA"], audience="authenticated")
    assert {"sub", "org", "sid", "azp"} <= set(claims) and claims["azp"] == "web"


def test_a_token_signed_by_any_other_key_is_refused(client, settings):
    other = SigningKeys.load(new_private_pem())
    forged = jwt.encode(
        {"sub": "x", "org": "y", "sid": "z", "aud": settings.jwt_audience, "iss": settings.jwt_issuer, "iat": 0, "exp": 9_999_999_999},
        other.private, algorithm="EdDSA", headers={"kid": settings.signing_keys.kid},
    )
    assert client.get("/auth/me", headers=bearer(forged)).status_code == 401


def test_signing_out_ends_the_session(client):
    headers = sign_in(client)
    assert client.get("/auth/me", headers=headers).status_code == 200
    assert client.post("/auth/logout", headers=headers).status_code == 204
    assert client.get("/auth/me", headers=headers).status_code == 401
    # Other sign-ins of the same person are their own sessions.
    other = sign_in(client)
    assert client.get("/auth/me", headers=other).status_code == 200


def test_the_orders_app_gets_the_same_session(client, orders_app):
    web = sign_in(client)
    verifier, challenge = pkce()
    r = code_for(client, web, challenge)
    assert r.status_code == 201, r.text
    assert r.json()["redirectUri"] == REDIRECT
    r = swap(client, r.json()["code"], verifier)
    assert r.status_code == 200, r.text
    orders = bearer(r.json()["accessToken"])
    assert r.json()["tokenType"] == "Bearer" and r.json()["expiresIn"] > 0
    me = client.get("/auth/me", headers=orders).json()
    assert me["user"]["email"] == "ana@pharmacrm.test" and me["org"]["slug"] == "getmeds"

    web_claims = jwt.decode(web["Authorization"][7:], options={"verify_signature": False})
    orders_claims = jwt.decode(orders["Authorization"][7:], options={"verify_signature": False})
    assert orders_claims["sid"] == web_claims["sid"] and orders_claims["azp"] == "orders"
    assert orders_claims["exp"] <= web_claims["exp"]

    # One sign-out: out of the Orders app means out of Orbit too.
    assert client.post("/auth/logout", headers=orders).status_code == 204
    assert client.get("/auth/me", headers=web).status_code == 401


def test_a_code_works_once_and_only_for_whoever_started_the_sign_in(client, orders_app):
    web = sign_in(client)
    verifier, challenge = pkce()
    code = code_for(client, web, challenge).json()["code"]
    assert swap(client, code, "x" * 43).status_code == 400  # wrong verifier: someone else's code
    assert swap(client, code, verifier).status_code == 400  # and now it's spent

    verifier, challenge = pkce()
    code = code_for(client, web, challenge).json()["code"]
    assert swap(client, code, verifier, secret="wrong-secret").status_code == 401
    assert swap(client, code, verifier, redirect="https://orders.example.test/other").status_code == 400
    assert swap(client, "made-up-code", verifier).status_code == 400


def test_codes_expire(client, app, orders_app):
    web = sign_in(client)
    verifier, challenge = pkce()
    code = code_for(client, web, challenge).json()["code"]
    with app.state.sessions() as db, all_companies(db):
        db.get(SsoCode, digest(code)).expires_at = utcnow() - timedelta(seconds=1)
        db.commit()
    assert swap(client, code, verifier).status_code == 400


def test_codes_only_go_to_registered_addresses_of_active_apps(client, app, orders_app):
    web = sign_in(client)
    _, challenge = pkce()
    assert code_for(client, web, challenge, redirect="https://evil.example.test/steal").status_code == 400
    assert code_for(client, web, challenge, client_id="nobody").status_code == 400
    with app.state.sessions() as db:
        db.get(SsoClient, "orders").revoked_at = utcnow()
        db.commit()
    assert code_for(client, web, challenge).status_code == 400


def test_a_code_is_worthless_once_its_session_ends(client, orders_app):
    web = sign_in(client)
    verifier, challenge = pkce()
    code = code_for(client, web, challenge).json()["code"]
    client.post("/auth/logout", headers=web)
    assert swap(client, code, verifier).status_code == 400


def test_switching_company_ends_the_old_session(client):
    headers = sign_in(client)
    me = client.get("/auth/orgs", headers=headers).json()
    r = client.post("/auth/switch-org", json={"orgId": me["current"]}, headers=headers)
    assert r.status_code == 200
    assert client.get("/auth/me", headers=headers).status_code == 401
    assert client.get("/auth/me", headers=bearer(r.json()["accessToken"])).status_code == 200


def test_the_client_tool_only_takes_safe_addresses():
    from app.tools.sso_client import checked_address

    assert checked_address("https://orders.example.test/sso/callback", production=True)
    assert checked_address("http://localhost:4000/sso/callback", production=False)
    for bad in ("http://orders.example.test/cb", "http://localhost:4000/cb#x", "javascript:alert(1)", "/relative"):
        with pytest.raises(SystemExit):
            checked_address(bad, production=bad.startswith("http://localhost") is False)
