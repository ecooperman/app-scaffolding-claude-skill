"""Who is making this request.

There are no passwords or sign-up forms: every request has already been
through Cloudflare Access, which attaches a signed token (Cf-Access-Jwt-
Assertion) carrying the signed-in person's email. shared_python.auth verifies
it (and refuses everything in production if that isn't configured, rather than
trusting the plain email header, which a hostname that bypasses Access would
let anyone forge); here it becomes this app's own User row, created the first
time we see them.

Use `current_user` on every route that touches a person's data, and
`require_admin` on anything only the app's owner should reach.
"""
import logging

from fastapi import Depends, HTTPException, Request
from shared_python import auth as cloudflare_access
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import config, models
from .deps import get_db

log = logging.getLogger(__name__)


def request_email(request: Request) -> str:
    """The verified email of whoever is asking (see shared_python/auth.py)."""
    return cloudflare_access.request_email(request, config.DEV_USER_EMAIL)


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
