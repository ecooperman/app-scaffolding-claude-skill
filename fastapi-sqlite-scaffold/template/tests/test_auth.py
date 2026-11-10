"""How this app uses Cloudflare Access's sign-in. The details of verifying the
token (audiences, expiry, signatures, the team-domain forms) are tested where
the code lives, in shared-python; this checks the app is wired to it and turns
the verified email into a user."""
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from shared_python import auth as shared_auth
from shared_python import settings

from app import auth, config, models

AUD = "test-aud-tag"


@pytest.fixture(scope="module")
def keypair():
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private, private.public_key()


def token(private, email="alice@example.com"):
    return jwt.encode({"email": email, "aud": [AUD], "exp": int(time.time()) + 300}, private, algorithm="RS256")


@pytest.fixture()
def production(monkeypatch, keypair):
    monkeypatch.setattr(settings, "ENV", "production")
    monkeypatch.setattr(settings, "CF_TEAM_DOMAIN", "team.cloudflareaccess.com")
    monkeypatch.setattr(settings, "CF_ACCESS_AUD", AUD)
    monkeypatch.setattr(shared_auth, "_signing_key", lambda _token: keypair[1])


def test_locally_with_no_header_you_are_the_dev_user(client):
    assert client.get("/api/me").json()["email"] == config.DEV_USER_EMAIL


def test_a_dev_user_cookie_plays_someone_else_locally(client):
    client.cookies.set("dev_user", "Bob@Example.com")
    assert client.get("/api/me").json()["email"] == "bob@example.com"


def test_the_user_is_created_once_on_first_sight_and_emails_are_lowercased(client, alice, db):
    first = alice.get("/api/me").json()
    again = alice.get("/api/me").json()
    assert first == again and first["email"] == "alice@example.com"
    assert db.query(models.User).filter_by(email="alice@example.com").count() == 1


def test_different_people_are_different_users(alice, bob):
    assert alice.get("/api/me").json()["id"] != bob.get("/api/me").json()["id"]


def test_me_says_whether_you_are_an_administrator(alice, bob, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_EMAILS", {"alice@example.com"})
    assert alice.get("/api/me").json()["is_admin"] is True
    assert bob.get("/api/me").json()["is_admin"] is False


def test_a_valid_token_identifies_the_person(client, production, keypair):
    resp = client.get("/api/me", headers={"Cf-Access-Jwt-Assertion": token(keypair[0], "Alice@Example.com")})
    assert resp.status_code == 200 and resp.json()["email"] == "alice@example.com"


def test_a_forged_plain_header_is_ignored_when_tokens_are_verified(client, production):
    assert client.get("/api/me", headers={"Cf-Access-Authenticated-User-Email": "alice@example.com"}).status_code == 401


def test_without_token_config_production_refuses_everything_even_with_the_header(client, monkeypatch):
    # A hostname that bypasses Access lets anyone send this header themselves.
    monkeypatch.setattr(settings, "ENV", "production")
    monkeypatch.setattr(settings, "CF_ACCESS_AUD", None)
    assert client.get("/api/me").status_code == 503
    assert client.get("/api/me", headers={"Cf-Access-Authenticated-User-Email": "alice@example.com"}).status_code == 503


def test_admin_emails_gate_admin_only_routes(monkeypatch):
    from fastapi import Depends, FastAPI
    from fastapi.testclient import TestClient

    from tests.conftest import Person

    mini = FastAPI()  # a stand-in app: the real one has no admin-only routes yet

    @mini.get("/admin-only", dependencies=[Depends(auth.require_admin)])
    def admin_only():
        return {"ok": True}

    monkeypatch.setattr(config, "ADMIN_EMAILS", {"alice@example.com"})
    client = TestClient(mini)
    assert Person(client, "alice@example.com").get("/admin-only").status_code == 200
    assert Person(client, "bob@example.com").get("/admin-only").status_code == 403
