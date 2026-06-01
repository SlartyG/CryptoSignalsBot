"""007 universe turnover, welcome snapshot, user events."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "007_v2_features"
down_revision: Union[str, None] = "006_channels_verified"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "market_universe",
        sa.Column("turnover_24h", sa.Float(), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("welcome_snapshot_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "user_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("event", sa.String(64), nullable=False, index=True),
        sa.Column("metadata", JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            index=True,
        ),
    )


def downgrade() -> None:
    op.drop_table("user_events")
    op.drop_column("users", "welcome_snapshot_at")
    op.drop_column("market_universe", "turnover_24h")
