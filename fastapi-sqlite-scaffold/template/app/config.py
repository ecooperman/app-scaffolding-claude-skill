import os

HOST = "__HOST__"
PORT = __PORT__

# "local" (default, for `uvicorn app.main:app --reload` on a dev machine) or
# "production" (set once, droplet-wide, via systemd's DefaultEnvironment -
# see DEPLOYMENT.md - so every app inherits it with no per-service config).
# Drives which shared-assets host the app's templates point at, so
# switching between local iteration and the real deploy never means
# hand-editing a URL and remembering to revert it.
ENV = os.environ.get("APP_ENV", "local")
SHARED_ASSETS_BASE = "https://static.evancooperman.com" if ENV == "production" else "http://127.0.0.1:8070"

# --- who is signed in (see app/auth.py) -------------------------------------
# There is no login form: Cloudflare Access authenticates everyone before a
# request reaches the app and attaches a signed token saying who it was.
# shared_python.auth verifies that token and, in production, REFUSES every
# request unless CF_TEAM_DOMAIN and CF_ACCESS_AUD are set. Those (and every other
# Cloudflare/notification setting) live in the shared secrets file every app
# reads (/etc/personal-apps/shared.env, see DEPLOYMENT.md and
# shared_python/settings.py), never in this repo.

# Locally there's no Cloudflare in front, so requests are treated as coming
# from this address; a Cf-Access-Authenticated-User-Email header or a
# `dev_user` cookie plays someone else (handy for testing sharing/isolation).
# Never used in production.
DEV_USER_EMAIL = os.environ.get("DEV_USER_EMAIL", "dev@localhost.test").strip().lower()

# Emails (comma-separated) that count as administrators - for features only
# the owner of the app should reach (see auth.require_admin). Locally it
# defaults to DEV_USER_EMAIL.
ADMIN_EMAILS = {e.strip().lower() for e in os.environ.get("ADMIN_EMAILS", "").split(",") if e.strip()}
if ENV != "production":
    ADMIN_EMAILS.add(DEV_USER_EMAIL)
# @@config@@
