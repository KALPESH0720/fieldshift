"""Persist owner-scoped NASA AppEEARS SMAP extraction jobs."""

from alembic import op
import sqlalchemy as sa


revision = "0012_nasa_smap_jobs"
down_revision = "0011_agmarknet_variety_identity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "satellite_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("farmer_id", sa.Integer(), sa.ForeignKey("farmers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("plot_id", sa.Integer(), sa.ForeignKey("plots.id", ondelete="CASCADE"), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(24), server_default="queued", nullable=False),
        sa.Column("provider_task_id", sa.String(80)),
        sa.Column("observations", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("error_code", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_satellite_jobs_farmer_created", "satellite_jobs", ["farmer_id", "created_at"])
    op.create_index("ix_satellite_jobs_plot_status", "satellite_jobs", ["plot_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_satellite_jobs_plot_status", table_name="satellite_jobs")
    op.drop_index("ix_satellite_jobs_farmer_created", table_name="satellite_jobs")
    op.drop_table("satellite_jobs")
