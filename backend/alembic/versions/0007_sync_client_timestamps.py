"""Persist accepted client versions for deterministic offline conflict resolution."""

from alembic import op
import sqlalchemy as sa

revision = "0007_sync_client_timestamps"
down_revision = "0006_sync_client_scope"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("plots", sa.Column("client_updated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("crop_records", sa.Column("client_updated_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("crop_records", "client_updated_at")
    op.drop_column("plots", "client_updated_at")
