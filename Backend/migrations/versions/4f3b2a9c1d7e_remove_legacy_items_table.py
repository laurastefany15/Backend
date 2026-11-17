"""Remove the legacy items table.

Revision ID: 4f3b2a9c1d7e
Revises: 0da526dd41e4
Create Date: 2026-10-14 16:31:00
"""
from alembic import op


revision = "4f3b2a9c1d7e"
down_revision = "0da526dd41e4"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("DROP TABLE IF EXISTS items")


def downgrade():
    pass
