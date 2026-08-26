"""add accommodation transaction ledger

Revision ID: ab12accommodation
Revises: 97efa9608e73
"""
from alembic import op
import sqlalchemy as sa

revision = "ab12accommodation"
down_revision = "97efa9608e73"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "accommodation_ledger_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("direction", sa.String(length=16), nullable=False),
        sa.Column("transaction_id", sa.String(length=255), nullable=False),
        sa.Column("message_id", sa.String(length=255), nullable=True),
        sa.Column("order_id", sa.String(length=255), nullable=True),
        sa.Column("state", sa.String(length=80), nullable=True),
        sa.Column("amount", sa.Float(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_accommodation_ledger_events_action", "accommodation_ledger_events", ["action"])
    op.create_index("ix_accommodation_ledger_events_transaction_id", "accommodation_ledger_events", ["transaction_id"])
    op.create_index("ix_accommodation_ledger_events_message_id", "accommodation_ledger_events", ["message_id"])
    op.create_index("ix_accommodation_ledger_events_order_id", "accommodation_ledger_events", ["order_id"])


def downgrade() -> None:
    op.drop_table("accommodation_ledger_events")
