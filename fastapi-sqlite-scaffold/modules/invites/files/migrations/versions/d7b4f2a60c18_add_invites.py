"""add invites

Requests for someone with no account to be let in, decided by the administrator
(see app/invites.py).

Revision ID: d7b4f2a60c18
Revises: __DOWN_REVISION__
Create Date: 2026-11-10 09:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd7b4f2a60c18'
down_revision: Union[str, Sequence[str], None] = '__DOWN_REVISION__'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "invites",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("invited_by_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["invited_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uq_invites_email"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("invites")
