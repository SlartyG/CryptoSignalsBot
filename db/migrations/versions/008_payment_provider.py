"""008 payment provider column."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "008_payment_provider"
down_revision: Union[str, None] = "007_v2_features"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "payments",
        sa.Column(
            "provider",
            sa.String(20),
            server_default="cryptopay",
            nullable=False,
        ),
    )
    op.create_index("ix_payments_provider", "payments", ["provider"])


def downgrade() -> None:
    op.drop_index("ix_payments_provider", table_name="payments")
    op.drop_column("payments", "provider")
