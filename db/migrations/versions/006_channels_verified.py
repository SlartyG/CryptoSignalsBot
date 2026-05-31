"""006 channel subscription verification."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "006_channels_verified"
down_revision: Union[str, None] = "005_admin_audit"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("channels_verified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        "UPDATE users SET channels_verified_at = consented_at WHERE consented_at IS NOT NULL"
    )


def downgrade() -> None:
    op.drop_column("users", "channels_verified_at")
