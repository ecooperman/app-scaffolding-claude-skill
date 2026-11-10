"""Asking for new people to be let in (anyone), and deciding on those requests
(the administrator only). The rules live in app/invites.py."""
from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import config, invites, models, notify, schemas
from ..auth import current_user, is_admin, require_admin
from ..deps import get_db

router = APIRouter(prefix="/api/invites", tags=["invites"])
admin_router = APIRouter(prefix="/api/admin/invites", tags=["invites"])


@router.get("", response_model=List[schemas.Invite])
def my_requests(user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    """The requests this person made, in any state."""
    return invites.mine(db, user)


@router.post("", response_model=schemas.Invite)
def ask(
    body: schemas.InviteCreate,
    background: BackgroundTasks,
    user: models.User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Ask for someone with no account to be let in. The administrator is told and
    decides. An administrator's own request is approved straight away."""
    email = invites.valid_email(body.email)
    if invites.can_sign_in(db, email):
        raise HTTPException(status_code=409, detail=f"{email} can already sign in, so there's nothing to request.")
    invite, problem = invites.create(db, user, email)
    if problem == "duplicate":
        earlier = db.query(models.Invite).filter_by(email=email).first()
        if earlier is not None and earlier.status == models.INVITE_DECLINED:
            detail = f"A request for {email} was declined. Only the administrator can let them in now."
        else:
            detail = f"A request for {email} is already waiting for the administrator to approve."
        raise HTTPException(status_code=409, detail=detail)
    if problem == "none_left":
        raise HTTPException(
            status_code=403,
            detail=f"You've used all {config.INVITES_PER_USER} of your invites. Only the administrator can raise the limit.",
        )
    if is_admin(user):
        return invites.approve(db, invite, background)
    background.add_task(notify.invite_requested, user.email, invite.email)
    return invite


@router.delete("/{invite_id}")
def withdraw(invite_id: int, user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    """Withdraw one of your own requests that's still waiting (this gives the invite back)."""
    invite = invites.get(db, invite_id)
    if invite is None or invite.invited_by_id != user.id:
        raise HTTPException(status_code=404, detail="Invite not found")
    if invite.status != models.INVITE_PENDING:
        raise HTTPException(status_code=409, detail="Only a request that's still waiting can be withdrawn")
    invites.cancel(db, invite)
    return {"ok": True}


# --- the administrator's side ------------------------------------------------


def _waiting(db: Session, invite_id: int) -> models.Invite:
    invite = invites.get(db, invite_id)
    if invite is None:
        raise HTTPException(status_code=404, detail="Invite not found")
    if invite.status != models.INVITE_PENDING:
        raise HTTPException(status_code=409, detail=f"That request was already {invite.status}")
    return invite


@admin_router.get("", response_model=List[schemas.AdminInvite])
def list_waiting(admin: models.User = Depends(require_admin), db: Session = Depends(get_db)):
    return invites.pending(db)


@admin_router.post("/{invite_id}/approve", response_model=schemas.AdminInvite)
def approve_invite(
    invite_id: int,
    background: BackgroundTasks,
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    invite = invites.approve(db, _waiting(db, invite_id), background)
    invite.invited_by_email = invite.invited_by.email
    return invite


@admin_router.post("/{invite_id}/decline", response_model=schemas.AdminInvite)
def decline_invite(invite_id: int, admin: models.User = Depends(require_admin), db: Session = Depends(get_db)):
    invite = invites.decline(db, _waiting(db, invite_id))
    invite.invited_by_email = invite.invited_by.email
    return invite
