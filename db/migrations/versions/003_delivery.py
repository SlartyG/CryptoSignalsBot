"""003 delivery and settings."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY

revision: str = "003_delivery"
down_revision: Union[str, None] = "002_signals"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_signal_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("signal_type", sa.String(32), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("symbols", ARRAY(sa.String(32)), nullable=True),
    )
    op.create_index("ix_user_signal_settings_user_id", "user_signal_settings", ["user_id"])

    op.create_table(
        "delivery_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("signal_id", sa.Integer(), sa.ForeignKey("signals_log.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
    )
    op.create_index("ix_delivery_log_signal_id", "delivery_log", ["signal_id"])
    op.create_index("ix_delivery_log_user_id", "delivery_log", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_delivery_log_user_id", "delivery_log")
    op.drop_index("ix_delivery_log_signal_id", "delivery_log")
    op.drop_table("delivery_log")
    op.drop_index("ix_user_signal_settings_user_id", "user_signal_settings")
    op.drop_table("user_signal_settings")
