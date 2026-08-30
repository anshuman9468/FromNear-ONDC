"""add durable BPP lifecycle state

Revision ID: c3b8f4d2a1e7
Revises: ab12accommodation
"""

from alembic import op
import sqlalchemy as sa


revision = "c3b8f4d2a1e7"
down_revision = "ab12accommodation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bpp_lifecycle_states",
        sa.Column("transaction_id", sa.String(length=255), primary_key=True),
        sa.Column("state", sa.JSON(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("bpp_lifecycle_states")
