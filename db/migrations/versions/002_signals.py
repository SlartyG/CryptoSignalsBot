"""002 signals and metrics."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "002_signals"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "signals_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("type", sa.String(32), nullable=False),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("payload_json", JSONB, nullable=False),
        sa.Column("confidence", sa.String(16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_signals_log_type", "signals_log", ["type"])
    op.create_index("ix_signals_log_symbol", "signals_log", ["symbol"])
    op.create_index("ix_signals_log_created_at", "signals_log", ["created_at"])

    op.create_table(
        "collector_metrics",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("collector_name", sa.String(64), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "ts",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_collector_metrics_name", "collector_metrics", ["collector_name"])
    op.create_index("ix_collector_metrics_ts", "collector_metrics", ["ts"])

    op.create_table(
        "market_universe",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("active_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("active_to", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_market_universe_symbol", "market_universe", ["symbol"])


def downgrade() -> None:
    op.drop_index("ix_market_universe_symbol", "market_universe")
    op.drop_table("market_universe")
    op.drop_index("ix_collector_metrics_ts", "collector_metrics")
    op.drop_index("ix_collector_metrics_name", "collector_metrics")
    op.drop_table("collector_metrics")
    op.drop_index("ix_signals_log_created_at", "signals_log")
    op.drop_index("ix_signals_log_symbol", "signals_log")
    op.drop_index("ix_signals_log_type", "signals_log")
    op.drop_table("signals_log")
