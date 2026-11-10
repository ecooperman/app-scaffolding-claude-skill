"""Who is making this request.

There are no passwords or sign-up forms: every request has already been
through Cloudflare Access, which attaches a signed token (Cf-Access-Jwt-
Assertion) carrying the signed-in person's email. We verify it, and create
that person's User row the first time we see them.

Production verifies the token's signature and audience against Cloudflare's
published keys (needs CF_TEAM_DOMAIN + CF_ACCESS_AUD, see config.py). Without
them it refuses every request rather than trusting the plain
Cf-Access-Authenticated-User-Email header: that header is only set by Access,
and a hostname that bypasses Access (or is misconfigured) lets a visitor send
any value they like, which would mean signing in as anyone.

Use `current_user` on every route that touches a person's data, and
`require_admin` on anything only the app's owner should reach.
"""
import logging
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import config, models
from .deps import get_db

log = logging.getLogger(__name__)

EMAIL_HEADER = "cf-access-authenticated-user-email"
JWT_HEADER = "cf-access-jwt-assertion"

_jwks_client: Optional[jwt.PyJWKClient] = None


def _signing_key(token: str):
    """Cloudflare's public key for this token (cached by PyJWKClient)."""
    global _jwks_client
    if _jwks_client is None:
        # Forgive a pasted "https://" or trailing slash - it's just a hostname.
        domain = config.CF_TEAM_DOMAIN.strip().removeprefix("https://").removeprefix("http://").rstrip("/")
        _jwks_client = jwt.PyJWKClient(f"https://{domain}/cdn-cgi/access/certs", lifespan=3600)
    return _jwks_client.get_signing_key_from_jwt(token).key


def _email_from_verified_token(token: str) -> str:
    try:
        claims = jwt.decode(
            token,
            _signing_key(token),
            algorithms=["RS256"],
            audience=[aud.strip() for aud in config.CF_ACCESS_AUD.split(",") if aud.strip()],
            options={"require": ["exp", "aud"]},
        )
    except jwt.PyJWTError as exc:
        log.warning("Rejected Cloudflare Access token: %s", exc)
        raise HTTPException(status_code=401, detail="Invalid sign-in token")
    email = claims.get("email")
    if not email:
        # e.g. a service token - it identifies a machine, not a person.
        raise HTTPException(status_code=401, detail="Sign-in token has no email")
    return email


def request_email(request: Request) -> str:
    headers = request.headers
    if config.ENV == "production":
        if not (config.CF_TEAM_DOMAIN and config.CF_ACCESS_AUD):
            log.error("CF_TEAM_DOMAIN and CF_ACCESS_AUD must be set in production - refusing all requests")
            raise HTTPException(status_code=503, detail="Sign-in is not configured on the server")
        token = headers.get(JWT_HEADER)
        if not token:
            raise HTTPException(status_code=401, detail="Not signed in")
        return _email_from_verified_token(token)
    # Local development: no Cloudflare, so a header or a `dev_user` cookie (set
    # it in the browser console: document.cookie = "dev_user=bob@example.com;
    # path=/") plays a second person; otherwise the configured dev user.
    return headers.get(EMAIL_HEADER) or request.cookies.get("dev_user") or config.DEV_USER_EMAIL


def normalize_email(email: str) -> str:
    return email.strip().lower()


def get_or_create_user(db: Session, email: str) -> models.User:
    """The person behind an (already normalized) email, created on first sight."""
    user = db.query(models.User).filter(models.User.email == email).first()
    if user is not None:
        return user
    user = models.User(email=email)
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        # Two first requests from the same person raced; theirs won.
        db.rollback()
        return db.query(models.User).filter(models.User.email == email).one()
    db.refresh(user)
    return user


def current_user(request: Request, db: Session = Depends(get_db)) -> models.User:
    email = normalize_email(request_email(request))
    if "@" not in email:
        raise HTTPException(status_code=401, detail="Not signed in")
    return get_or_create_user(db, email)


def is_admin(user: models.User) -> bool:
    return user.email in config.ADMIN_EMAILS


def require_admin(user: models.User = Depends(current_user)) -> models.User:
    if not is_admin(user):
        raise HTTPException(status_code=403, detail="Only the app's administrator can do that")
    return user
