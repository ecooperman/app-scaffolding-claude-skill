"""People's own API keys: stored encrypted, never shown again, and the rule for
whose key a paid call uses - their own, else the house key for an administrator
and nobody else. The call to the provider is stubbed."""
import logging

import pytest

from app import apikeys, config, models

ALICE_KEY = "sk-ant-alice-0123456789abcdef"
BOB_KEY = "sk-ant-bob---0123456789wxyz"
HOUSE_KEY = "sk-ant-HOUSE-0123456789house"


@pytest.fixture()
def accepted(monkeypatch):
    """The service accepts every key (the live check is stubbed)."""
    monkeypatch.setattr(apikeys, "verify", lambda provider, key: (True, ""))


@pytest.fixture()
def house(monkeypatch):
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", HOUSE_KEY)


@pytest.fixture()
def admin_alice(monkeypatch, alice):
    monkeypatch.setattr(config, "ADMIN_EMAILS", {alice.email})
    return alice


def save(person, provider, key):
    return person.put(f"/api/profile/api-keys/{provider}", {"key": key})


def mine(person, provider="anthropic"):
    return next(k for k in person.get("/api/profile/api-keys").json()["keys"] if k["provider"] == provider)


# --- storing a key ------------------------------------------------------------


def test_a_saved_key_is_encrypted_in_the_database_and_never_sent_back(alice, accepted, db):
    resp = save(alice, "anthropic", ALICE_KEY)
    assert resp.status_code == 200 and resp.json()["verified"] is True
    row = db.query(models.UserApiKey).one()
    assert ALICE_KEY not in row.encrypted_key and row.last4 == "cdef"
    for body in (resp.text, alice.get("/api/profile/api-keys").text):
        assert ALICE_KEY not in body and "encrypted_key" not in body
    assert mine(alice)["has_own_key"] is True and mine(alice)["last4"] == "cdef"


def test_keys_belong_to_one_person_each(alice, bob, accepted):
    save(alice, "anthropic", ALICE_KEY)
    assert mine(bob)["has_own_key"] is False
    assert bob.delete("/api/profile/api-keys/anthropic").status_code == 404  # nothing of theirs to remove
    assert mine(alice)["has_own_key"] is True


def test_replacing_and_removing_a_key(alice, accepted, db):
    save(alice, "anthropic", ALICE_KEY)
    save(alice, "anthropic", BOB_KEY)
    assert db.query(models.UserApiKey).count() == 1 and mine(alice)["last4"] == "wxyz"
    assert alice.delete("/api/profile/api-keys/anthropic").status_code == 200
    assert db.query(models.UserApiKey).count() == 0


def test_a_key_the_service_refuses_is_not_saved(alice, db, monkeypatch):
    monkeypatch.setattr(apikeys, "verify", lambda provider, key: (False, "Anthropic didn't accept that key"))
    resp = save(alice, "anthropic", ALICE_KEY)
    assert resp.status_code == 400 and "didn't accept" in resp.json()["detail"]
    assert db.query(models.UserApiKey).count() == 0


def test_a_key_that_could_not_be_checked_is_saved_and_said_to_be_unverified(alice, monkeypatch):
    monkeypatch.setattr(apikeys, "verify", lambda provider, key: (None, "Couldn't reach Anthropic to check the key"))
    resp = save(alice, "anthropic", ALICE_KEY)
    assert resp.status_code == 200 and resp.json()["verified"] is None and "not verified" in resp.json()["note"]


def test_something_that_is_not_a_key_is_refused_before_any_call(alice, monkeypatch):
    monkeypatch.setattr(apikeys, "verify", lambda *a: pytest.fail("a malformed key must not reach the service"))
    assert save(alice, "anthropic", "too short").status_code == 400


def test_an_unknown_service_is_a_404(alice, accepted):
    assert save(alice, "nonsense", ALICE_KEY).status_code == 404
    assert alice.delete("/api/profile/api-keys/nonsense").status_code == 404


def test_without_an_encryption_secret_production_refuses_to_save(alice, accepted, monkeypatch):
    monkeypatch.setattr(apikeys, "storage_available", lambda: False)
    assert save(alice, "anthropic", ALICE_KEY).status_code == 503
    assert alice.get("/api/profile/api-keys").json()["can_save"] is False


def test_a_key_saved_under_another_secret_is_unreadable_not_leaked(alice, accepted, monkeypatch, caplog, db):
    from shared_python import settings

    monkeypatch.setattr(settings, "KEY_ENCRYPTION_SECRET", "the-original-secret-long-enough")
    save(alice, "anthropic", ALICE_KEY)
    monkeypatch.setattr(settings, "KEY_ENCRYPTION_SECRET", "a-different-secret-entirely-now")
    user = db.query(models.User).filter_by(email=alice.email).one()
    with caplog.at_level(logging.WARNING):
        assert apikeys.resolve(db, user, "anthropic") is None
    assert "could not be decrypted" in caplog.text and ALICE_KEY not in caplog.text
    assert mine(alice)["own_key_readable"] is False and mine(alice)["usable"] is False


# --- whose key a call uses ----------------------------------------------------


def test_the_house_key_is_for_administrators_only(db, alice, bob, house, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_EMAILS", {alice.email})
    alice.get("/api/me"), bob.get("/api/me")
    admin = db.query(models.User).filter_by(email=alice.email).one()
    other = db.query(models.User).filter_by(email=bob.email).one()
    assert apikeys.resolve(db, admin, "anthropic") == HOUSE_KEY
    assert apikeys.resolve(db, other, "anthropic") is None


def test_an_own_key_beats_the_house_key_even_for_an_administrator(admin_alice, house, accepted, db):
    save(admin_alice, "anthropic", ALICE_KEY)
    user = db.query(models.User).filter_by(email=admin_alice.email).one()
    assert apikeys.resolve(db, user, "anthropic") == ALICE_KEY


def test_a_non_administrator_with_their_own_key_can_use_the_feature(bob, house, accepted, db):
    save(bob, "anthropic", BOB_KEY)
    user = db.query(models.User).filter_by(email=bob.email).one()
    assert apikeys.require(db, user, "anthropic") == BOB_KEY


def test_without_a_key_the_feature_says_how_to_turn_it_on(bob, house, db):
    bob.get("/api/me")
    user = db.query(models.User).filter_by(email=bob.email).one()
    with pytest.raises(apikeys.HTTPException) as exc:
        apikeys.require(db, user, "anthropic")
    assert exc.value.status_code == 400 and "Profile page" in exc.value.detail


def test_me_says_which_services_you_can_use(admin_alice, bob, house):
    assert admin_alice.get("/api/me").json()["can_use"] == {"anthropic": True}
    assert bob.get("/api/me").json()["can_use"] == {"anthropic": False}


# --- the live check -----------------------------------------------------------


def test_checking_a_key_never_raises_and_never_echoes_it(monkeypatch, caplog):
    import requests

    def boom(*a, **k):
        raise requests.ConnectionError(f"HTTPSConnectionPool(host='x'): key={ALICE_KEY}")

    monkeypatch.setattr(requests, "get", boom)
    with caplog.at_level(logging.WARNING):
        result = apikeys.verify("anthropic", ALICE_KEY)
    assert result[0] is None and ALICE_KEY not in result[1]
    assert ALICE_KEY not in caplog.text and "ConnectionError" in caplog.text
