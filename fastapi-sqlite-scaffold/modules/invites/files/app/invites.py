"""Letting new people into the app itself.

Anyone can ask for a person with no account to be let in; the administrator
decides. Approving adds the email to the Cloudflare Access group that lets people
through the login gate (shared_python.cloudflare) and gives them an account here.
Each person may ask for a limited number (INVITES_PER_USER, administrators are
unlimited and approved straight away). Nothing here shares anything with the new
person: what they can then see is decided by the app's own tables (owner_id).

Heads up: the Cloudflare group is shared by every app on the shared-apps Access
application, so being let in here lets the person through the gate for all of them
(they would just have an empty account elsewhere). See DEPLOYMENT.md.
"""
import re
from datetime import datetime

from fastapi import BackgroundTasks, HTTPException
from shared_python import cloudflare
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from . import auth, config, models, notify

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def valid_email(raw: str) -> str:
    email = auth.normalize_email(raw)
    if not _EMAIL.match(email):
        raise HTTPException(status_code=400, detail="That doesn't look like an email address")
    return email


def can_sign_in(db: Session, email: str) -> bool:
    """Whether this person can get in right now. Cloudflare decides who passes
    the login gate, so it's asked rather than inferring it from an account
    existing. With Cloudflare unconfigured (local development) all there is to go
    on is whether they've signed in."""
    try:
        let_in = cloudflare.is_let_in(email, config.ADMIN_EMAILS)
    except cloudflare.CloudflareError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    if let_in is None:
        return db.query(models.User).filter(models.User.email == email).first() is not None
    return let_in


def invites_left(db: Session, user: models.User):
    """How many more people this person may ask for, or None for no limit
    (administrators). Each different email they've asked for counts once, in any
    state - waiting, approved, declined - until they withdraw a waiting one, so
    being refused doesn't hand the slot back to be spent again."""
    if auth.is_admin(user):
        return None
    used = db.query(func.count(func.distinct(models.Invite.email))).filter(models.Invite.invited_by_id == user.id).scalar()
    return max(config.INVITES_PER_USER - used, 0)


def create(db: Session, inviter: models.User, email: str):
    """Returns (invite, None), or (None, reason) with reason "duplicate" (someone
    already asked for this person) or "none_left"."""
    if db.query(models.Invite).filter_by(email=email).first() is not None:
        return None, "duplicate"
    left = invites_left(db, inviter)
    if left is not None and left <= 0:
        return None, "none_left"
    invite = models.Invite(email=email, invited_by_id=inviter.id)
    db.add(invite)
    try:
        db.commit()
    except IntegrityError:  # the same request raced in twice
        db.rollback()
        return None, "duplicate"
    db.refresh(invite)
    return invite, None


def get(db: Session, invite_id: int):
    return (
        db.query(models.Invite).options(joinedload(models.Invite.invited_by)).filter(models.Invite.id == invite_id).first()
    )


def mine(db: Session, user: models.User):
    return db.query(models.Invite).filter_by(invited_by_id=user.id).order_by(models.Invite.id).all()


def pending(db: Session):
    waiting = (
        db.query(models.Invite)
        .options(joinedload(models.Invite.invited_by))
        .filter(models.Invite.status == models.INVITE_PENDING)
        .order_by(models.Invite.id)
        .all()
    )
    for invite in waiting:
        invite.invited_by_email = invite.invited_by.email
    return waiting


def pending_count(db: Session) -> int:
    return db.query(models.Invite).filter(models.Invite.status == models.INVITE_PENDING).count()


def cancel(db: Session, invite: models.Invite) -> None:
    db.delete(invite)
    db.commit()


def decline(db: Session, invite: models.Invite) -> models.Invite:
    invite.status = models.INVITE_DECLINED
    invite.decided_at = datetime.utcnow()
    db.commit()
    return invite


def approve(db: Session, invite: models.Invite, background: BackgroundTasks) -> models.Invite:
    """Let the person through Cloudflare's login gate, give them an account, then
    tell them by email. The Cloudflare step goes first: if it fails the request
    stays waiting, so nobody is recorded as let in who still can't sign in."""
    try:
        cloudflare.allow_email(invite.email)
    except cloudflare.NotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except cloudflare.SeatCapReached as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except cloudflare.CloudflareError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    auth.get_or_create_user(db, invite.email)
    invite.status = models.INVITE_APPROVED
    invite.decided_at = datetime.utcnow()
    db.commit()
    # Plain values, not the ORM objects: this runs after the response, when the
    # request's session is closed.
    background.add_task(notify.tell_let_in, invite.email, invite.invited_by.email)
    return invite
