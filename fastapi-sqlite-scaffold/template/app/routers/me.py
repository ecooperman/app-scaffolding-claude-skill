from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, schemas
# @@me_imports@@
from ..auth import current_user, is_admin
from ..deps import get_db

router = APIRouter(prefix="/api/me", tags=["me"])


@router.get("", response_model=schemas.Me)
def get_me(user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    return schemas.Me(
        id=user.id,
        email=user.email,
        is_admin=is_admin(user),
        # @@me_args@@
    )
