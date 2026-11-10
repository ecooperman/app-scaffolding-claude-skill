"""Telling people things - the sending lives in shared_python.notify; this is
where this app's own wording and links go."""
from shared_python import notify as shared
from shared_python.notify import describe_failure, notify, send_email  # noqa: F401 - re-exported

from . import config

APP_NAME = "__PROJECT_TITLE__"


def invite_requested(inviter_email: str, invitee_email: str) -> None:
    """Tell the administrator someone asked for a new person to be let in."""
    shared.invite_requested(APP_NAME, inviter_email, invitee_email, None, f"{config.PUBLIC_URL}/invites.html")


def tell_let_in(to: str, inviter_email: str) -> None:
    """Email someone that they've been let into the app."""
    shared.tell_let_in(to, inviter_email, APP_NAME, config.PUBLIC_URL)
