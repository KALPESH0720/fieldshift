"""Scope offline operation idempotency keys to the submitting client."""

from alembic import op
import sqlalchemy as sa

revision = "0006_sync_client_scope"
down_revision = "0005_recommendation_knowledge"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("uq_sync_operation_farmer_operation", "sync_operation_logs", type_="unique")
    op.add_column("sync_operation_logs", sa.Column("client_id", sa.String(length=128), nullable=False,
                                                     server_default="legacy"))
    op.alter_column("sync_operation_logs", "client_id", server_default=None)
    op.create_unique_constraint(
        "uq_sync_operation_farmer_client_operation", "sync_operation_logs",
        ["farmer_id", "client_id", "operation_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_sync_operation_farmer_client_operation", "sync_operation_logs", type_="unique")
    op.drop_column("sync_operation_logs", "client_id")
    op.create_unique_constraint("uq_sync_operation_farmer_operation", "sync_operation_logs",
                                ["farmer_id", "operation_id"])
