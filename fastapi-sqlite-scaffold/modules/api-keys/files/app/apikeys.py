"""People's own API keys for the paid services the app can call.

Instead of metering strangers on the owner's bill, each person brings their own
key for a paid service (Anthropic here; add more in PROVIDERS). Which key a call uses:

1. the signed-in person's own saved key, if they have one;
2. otherwise the server's own ("house") key from the environment - but ONLY for
   an administrator. Anyone else without a key of their own just doesn't have
   that feature, and is told how to turn it on (see require()).

Saved keys are encrypted with KEY_ENCRYPTION_SECRET, never sent back to the
browser (only the last four characters are kept in the clear), and never logged
- see shared_python/keystore.py, which does the encrypting and its limits.

Using a key in a route:

    key = apikeys.require(db, user, "anthropic")   # or apikeys.resolve() to get None instead of a 400

To add a service: a Provider entry in PROVIDERS (with the env var the house key is
read from, set up in config.py), and a `_verify_<id>` function registered in
_VERIFIERS that makes one tiny real call so a typo is caught on the Profile page.
"""
import logging
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

import requests
from fastapi import HTTPException
from shared_python import keystore
from shared_python.keystore import KeyStorageNotConfigured, clean, scrub, storage_available  # noqa: F401 (the routes use these)
from sqlalchemy.orm import Session

from . import config, models

log = logging.getLogger(__name__)

TIMEOUT = 10


@dataclass(frozen=True)
class Provider:
    id: str
    label: str
    feature: str  # shown to the person: "<feature> needs your own <label> key"
    description: str
    optional: bool  # the feature works without it, just less well
    get_url: str  # where to create a key
    house: Callable[[], Optional[str]]


def _house_anthropic():
    return config.ANTHROPIC_API_KEY


PROVIDERS: Dict[str, Provider] = {
    "anthropic": Provider(
        id="anthropic",
        label="Anthropic",
        feature="AI features",  # name what the key turns on, e.g. "Reading listings"
        description="Lets the app use Claude on your own Anthropic account, which bills you directly for what you use.",
        optional=False,
        get_url="https://console.anthropic.com/settings/keys",
        house=_house_anthropic,
    ),
}


# --- saving, reading, removing -----------------------------------------------


def save(db: Session, user: models.User, provider: str, raw_key: str) -> models.UserApiKey:
    key = clean(raw_key)
    token = keystore.encrypt(key)
    row = db.query(models.UserApiKey).filter_by(user_id=user.id, provider=provider).first()
    if row is None:
        row = models.UserApiKey(user_id=user.id, provider=provider, encrypted_key=token, last4=keystore.last4(key))
        db.add(row)
    else:
        row.encrypted_key, row.last4 = token, keystore.last4(key)
    db.commit()
    db.refresh(row)
    return row


def remove(db: Session, user: models.User, provider: str) -> bool:
    row = db.query(models.UserApiKey).filter_by(user_id=user.id, provider=provider).first()
    if row is None:
        return False
    db.delete(row)
    db.commit()
    return True


def _row(db: Session, user: models.User, provider: str) -> Optional[models.UserApiKey]:
    return db.query(models.UserApiKey).filter_by(user_id=user.id, provider=provider).first()


def _decrypt(row: models.UserApiKey) -> Optional[str]:
    """The saved key, or None if it can't be read (the secret changed, or the
    server has none)."""
    return keystore.decrypt(row.encrypted_key, row.provider)


def can_use_house_key(user: models.User) -> bool:
    """Only administrators spend the server's own keys."""
    return user.email in config.ADMIN_EMAILS


def resolve(db: Session, user: models.User, provider: str) -> Optional[str]:
    """The key to use for this person, or None (see the module docstring)."""
    row = _row(db, user, provider)
    if row is not None:
        own = _decrypt(row)
        if own:
            return own
    if can_use_house_key(user):
        return PROVIDERS[provider].house() or None
    return None


def require(db: Session, user: models.User, provider: str) -> str:
    """resolve(), or a plain explanation of how to turn the feature on."""
    key = resolve(db, user, provider)
    if key:
        return key
    p = PROVIDERS[provider]
    raise HTTPException(
        status_code=400,
        detail=f"{p.feature} needs your own {p.label} key - add it on your Profile page.",
    )


def available(db: Session, user: models.User) -> Dict[str, bool]:
    """Which services this person can use right now (own key, or the house key
    if they're an administrator) - for the pages to show or hide features."""
    return {pid: resolve(db, user, pid) is not None for pid in PROVIDERS}


def status(db: Session, user: models.User) -> List[dict]:
    out = []
    house_ok = can_use_house_key(user)
    for p in PROVIDERS.values():
        row = _row(db, user, p.id)
        readable = row is not None and _decrypt(row) is not None
        house_key = bool(house_ok and p.house())
        out.append(
            {
                "provider": p.id,
                "label": p.label,
                "feature": p.feature,
                "description": p.description,
                "optional": p.optional,
                "get_url": p.get_url,
                "has_own_key": row is not None,
                "own_key_readable": readable if row is not None else True,
                "last4": row.last4 if row is not None else None,
                "added_at": row.updated_at if row is not None else None,
                "using_house_key": house_key and not readable,
                "usable": readable or house_key,
            }
        )
    return out


# --- checking a key before it's saved ---------------------------------------
#
# One tiny real call per provider, so a typo is caught while the person is still
# on the page. Returns (True, "") if the provider accepted it, (False, why) if it
# refused it, or (None, why) if we couldn't tell (the service was unreachable) -
# in which case the key is saved anyway and the person is told it wasn't verified.


def _verify_anthropic(key: str) -> Tuple[Optional[bool], str]:
    r = requests.get(
        "https://api.anthropic.com/v1/models",
        params={"limit": 1},
        headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
        timeout=TIMEOUT,
    )
    if r.status_code in (401, 403):
        return False, "Anthropic didn't accept that key"
    if r.ok:
        return True, ""
    return None, f"Anthropic answered with an error ({r.status_code})"


_VERIFIERS = {"anthropic": _verify_anthropic}


def verify(provider: str, key: str) -> Tuple[Optional[bool], str]:
    try:
        return _VERIFIERS[provider](key)
    except (requests.RequestException, ValueError) as exc:
        # The type only: a library's message can echo the URL, and a URL can carry the key.
        log.warning("Checking a %s key failed: %s", provider, type(exc).__name__)
        return None, f"Couldn't reach {PROVIDERS[provider].label} to check the key"
