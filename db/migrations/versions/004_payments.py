"""004 payments."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004_payments"
down_revision: Union[str, None] = "003_delivery"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("invoice_id", sa.String(64), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False),
        sa.Column("amount_usdt", sa.Float(), nullable=False),
        sa.Column("plan", sa.String(10), nullable=False),
        sa.Column("status", sa.String(20), server_default="pending", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_payments_user_id", "payments", ["user_id"])
    op.create_index("ix_payments_invoice_id", "payments", ["invoice_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_payments_invoice_id", "payments")
    op.drop_index("ix_payments_user_id", "payments")
    op.drop_table("payments")
