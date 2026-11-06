"""Add update timestamps and durable offline-sync event/idempotency tables."""

from alembic import op
import sqlalchemy as sa

revision = "0002_sync_delta"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("plots", sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.add_column("crop_records", sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_table(
        "sync_operation_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("farmer_id", sa.Integer(), sa.ForeignKey("farmers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("operation_id", sa.String(128), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("farmer_id", "operation_id", name="uq_sync_operation_farmer_operation"),
    )
    op.create_index("ix_sync_operation_logs_farmer_id", "sync_operation_logs", ["farmer_id"])
    op.create_table(
        "sync_changes",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("farmer_id", sa.Integer(), sa.ForeignKey("farmers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entity", sa.String(64), nullable=False),
        sa.Column("entity_id", sa.String(128), nullable=False),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_sync_changes_farmer_id", "sync_changes", ["farmer_id"])


def downgrade() -> None:
    op.drop_table("sync_changes")
    op.drop_table("sync_operation_logs")
    op.drop_column("crop_records", "updated_at")
    op.drop_column("plots", "updated_at")
