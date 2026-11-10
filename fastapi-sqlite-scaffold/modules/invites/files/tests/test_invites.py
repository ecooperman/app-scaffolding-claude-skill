"""Letting new people into the app: anyone asks, the administrator decides. The
Cloudflare call and the notifications are stubbed here (shared-python's own tests
cover those); what matters in this file is who may ask and decide, how many times,
and what each outcome leaves behind."""
import smtplib

import pytest
import requests
from shared_python import cloudflare, notify
from shared_python import settings as shared_settings

from app import config, models

NEWBIE = "newbie@example.com"


@pytest.fixture(autouse=True)
def _nothing_leaves_the_machine(monkeypatch):
    """Whatever is set in the developer's shell, a test must never reach out with
    it: the settings are blanked, and any HTTP or SMTP call a test didn't stub fails."""
    for name in (
        "CF_API_TOKEN", "CF_ACCOUNT_ID", "CF_INVITEES_GROUP_ID", "NTFY_TOPIC", "NTFY_TOKEN",
        "PUSHOVER_APP_TOKEN", "PUSHOVER_USER_KEY", "SMTP_HOST", "SMTP_USERNAME", "SMTP_PASSWORD",
        "SMTP_FROM", "NOTIFY_EMAIL",
    ):
        monkeypatch.setattr(shared_settings, name, None)
    monkeypatch.setattr(config, "INVITES_PER_USER", 5)

    def refuse(*args, **kwargs):
        raise AssertionError(f"a test made a real network call: {args[:2]}")

    for target, name in ((requests, "request"), (requests, "post"), (smtplib, "SMTP"), (smtplib, "SMTP_SSL")):
        monkeypatch.setattr(target, name, refuse)


@pytest.fixture()
def allowed(monkeypatch):
    """Stand-in for Cloudflare: the emails that were let through the gate."""
    emails = []
    monkeypatch.setattr(cloudflare, "allow_email", emails.append)
    return emails


@pytest.fixture()
def alerts(monkeypatch):
    """Stand-in for the administrator's alert channels."""
    messages = []
    monkeypatch.setattr(notify, "notify", lambda title, message, link=None: messages.append((title, message, link)))
    return messages


@pytest.fixture()
def emailed(monkeypatch):
    """Stand-in for email: (to, subject, body) of each message sent."""
    sent = []
    monkeypatch.setattr(notify, "send_email", lambda to, subject, body: sent.append((to, subject, body)) or True)
    return sent


@pytest.fixture()
def admin(monkeypatch, client):
    from tests.conftest import Person

    boss = Person(client, "boss@example.com")
    monkeypatch.setattr(config, "ADMIN_EMAILS", {boss.email})
    return boss


def ask(person, email=NEWBIE):
    return person.post("/api/invites", {"email": email})


# --- asking -------------------------------------------------------------------


def test_asking_for_a_new_person_waits_for_approval(alice, admin, allowed, alerts):
    resp = ask(alice, "  NewBie@Example.com ")
    assert resp.status_code == 200
    assert resp.json()["email"] == NEWBIE and resp.json()["status"] == "pending"
    assert allowed == []  # nobody is let through until the administrator says so
    assert admin.get("/api/me").json()["pending_invites"] == 1


def test_the_administrator_is_told_about_each_request(alice, admin, allowed, alerts):
    ask(alice)
    assert len(alerts) == 1
    title, message, link = alerts[0]
    assert "invite waiting for approval" in title
    assert alice.email in message and NEWBIE in message and "(can" not in message
    assert link.endswith("/invites.html")


def test_a_failing_alert_doesnt_fail_the_request(alice, admin, allowed, monkeypatch):
    def broken(title, message, link):
        raise RuntimeError("push service is down")

    monkeypatch.setattr(notify, "CHANNELS", {"ntfy": broken})
    assert ask(alice).status_code == 200


def test_an_administrators_own_request_is_approved_straight_away(admin, allowed, alerts, emailed):
    resp = ask(admin)
    assert resp.status_code == 200 and resp.json()["status"] == "approved"
    assert allowed == [NEWBIE]
    assert alerts == []  # they decided it themselves, nobody to ask
    assert emailed and emailed[0][0] == NEWBIE


def test_a_bad_address_is_refused(alice):
    assert ask(alice, "not-an-email").status_code == 400


def test_someone_who_can_already_sign_in_is_not_invited(alice, bob, allowed):
    bob.get("/api/me")  # an account exists, and with no Cloudflare to ask that is what counts
    resp = ask(alice, bob.email)
    assert resp.status_code == 409 and "already sign in" in resp.json()["detail"]
    assert db_count(alice) == 0


def db_count(person):
    return len(person.get("/api/invites").json())


def test_a_repeat_request_is_refused_whoever_makes_it(alice, bob, allowed, alerts):
    assert ask(alice).status_code == 200
    again = ask(bob)
    assert again.status_code == 409 and "already waiting" in again.json()["detail"]
    assert ask(alice).status_code == 409


def test_a_declined_person_cant_be_asked_for_again(alice, bob, admin, allowed, alerts):
    invite = ask(alice).json()
    assert admin.post(f"/api/admin/invites/{invite['id']}/decline").status_code == 200
    resp = ask(bob)
    assert resp.status_code == 409 and "declined" in resp.json()["detail"]


# --- the allowance ------------------------------------------------------------


def test_everyone_gets_a_limited_number_of_invites_and_the_administrator_none_limit(alice, admin, allowed, alerts, monkeypatch):
    monkeypatch.setattr(config, "INVITES_PER_USER", 2)
    assert alice.get("/api/me").json()["invites_left"] == 2
    assert ask(alice, "a@example.com").status_code == 200
    assert ask(alice, "b@example.com").status_code == 200
    third = ask(alice, "c@example.com")
    assert third.status_code == 403 and "used all 2" in third.json()["detail"]
    assert alice.get("/api/me").json()["invites_left"] == 0
    assert admin.get("/api/me").json()["invites_left"] is None
    for n in range(4):
        assert ask(admin, f"x{n}@example.com").status_code == 200


def test_withdrawing_a_waiting_request_gives_the_invite_back(alice, allowed, alerts):
    invite = ask(alice).json()
    left = alice.get("/api/me").json()["invites_left"]
    assert alice.delete(f"/api/invites/{invite['id']}").status_code == 200
    assert alice.get("/api/me").json()["invites_left"] == left + 1
    assert alice.get("/api/invites").json() == []


def test_a_declined_request_still_counts_against_the_allowance(alice, admin, allowed, alerts):
    invite = ask(alice).json()
    before = alice.get("/api/me").json()["invites_left"]
    admin.post(f"/api/admin/invites/{invite['id']}/decline")
    assert alice.get("/api/me").json()["invites_left"] == before


def test_only_your_own_waiting_requests_can_be_withdrawn(alice, bob, admin, allowed, alerts):
    invite = ask(alice).json()
    assert bob.delete(f"/api/invites/{invite['id']}").status_code == 404
    admin.post(f"/api/admin/invites/{invite['id']}/approve")
    assert alice.delete(f"/api/invites/{invite['id']}").status_code == 409  # decided: too late


def test_people_see_only_their_own_requests(alice, bob, allowed, alerts):
    ask(alice)
    assert len(alice.get("/api/invites").json()) == 1
    assert bob.get("/api/invites").json() == []


# --- the administrator decides -------------------------------------------------


def test_approving_lets_them_through_gives_them_an_account_and_emails_them(alice, admin, allowed, alerts, emailed, db):
    invite = ask(alice).json()
    resp = admin.post(f"/api/admin/invites/{invite['id']}/approve")
    assert resp.status_code == 200 and resp.json()["status"] == "approved" and resp.json()["invited_by_email"] == alice.email
    assert allowed == [NEWBIE]
    assert db.query(models.User).filter_by(email=NEWBIE).count() == 1
    to, subject, body = emailed[0]
    assert to == NEWBIE and alice.email in subject and NEWBIE in body  # tells them which address to sign in with


def test_if_cloudflare_refuses_the_request_stays_waiting(alice, admin, monkeypatch, alerts, db):
    def refuse(email):
        raise cloudflare.SeatCapReached("The Access group is full (50 people).")

    monkeypatch.setattr(cloudflare, "allow_email", refuse)
    invite = ask(alice).json()
    resp = admin.post(f"/api/admin/invites/{invite['id']}/approve")
    assert resp.status_code == 409 and "full" in resp.json()["detail"]
    assert db.query(models.Invite).one().status == models.INVITE_PENDING
    assert db.query(models.User).filter_by(email=NEWBIE).count() == 0


def test_declining_emails_nobody_and_leaves_no_account(alice, admin, allowed, alerts, emailed, db):
    invite = ask(alice).json()
    assert admin.post(f"/api/admin/invites/{invite['id']}/decline").json()["status"] == "declined"
    assert emailed == [] and allowed == []
    assert db.query(models.User).filter_by(email=NEWBIE).count() == 0


def test_a_request_can_only_be_decided_once(alice, admin, allowed, alerts):
    invite = ask(alice).json()
    admin.post(f"/api/admin/invites/{invite['id']}/decline")
    assert admin.post(f"/api/admin/invites/{invite['id']}/approve").status_code == 409
    assert admin.post("/api/admin/invites/999/approve").status_code == 404


def test_only_the_administrator_sees_or_decides_requests(alice, bob, admin, allowed, alerts):
    invite = ask(alice).json()
    for person in (alice, bob):
        assert person.get("/api/admin/invites").status_code == 403
        assert person.post(f"/api/admin/invites/{invite['id']}/approve").status_code == 403
        assert person.post(f"/api/admin/invites/{invite['id']}/decline").status_code == 403
    waiting = admin.get("/api/admin/invites").json()
    assert [w["email"] for w in waiting] == [NEWBIE] and waiting[0]["invited_by_email"] == alice.email
    assert alice.get("/api/me").json()["pending_invites"] == 0  # the count is the administrator's alone
