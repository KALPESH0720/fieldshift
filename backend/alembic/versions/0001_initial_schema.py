"""Initial Field Shift schema.

Revision ID: 0001_initial_schema
Revises:
"""

from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geometry

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.create_table(
        "farmers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("phone", sa.String(20), nullable=False, unique=True),
        sa.Column("name", sa.String(120)),
        sa.Column("language", sa.String(16), nullable=False, server_default="en"),
        sa.Column("village", sa.String(120)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_farmers_phone", "farmers", ["phone"])
    op.create_table(
        "seasons",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(80), nullable=False, unique=True),
        sa.Column("start_month", sa.Integer(), nullable=False),
        sa.Column("end_month", sa.Integer(), nullable=False),
        sa.CheckConstraint("start_month BETWEEN 1 AND 12", name="ck_seasons_start_month"),
        sa.CheckConstraint("end_month BETWEEN 1 AND 12", name="ck_seasons_end_month"),
    )
    op.create_table(
        "crop_rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("crop_name", sa.String(120), nullable=False, unique=True),
        sa.Column("crop_family", sa.String(80)),
        sa.Column("root_depth", sa.String(32)),
        sa.Column("water_requirement", sa.String(32)),
        sa.Column("nitrogen_effect", sa.Numeric(8, 3)),
        sa.Column("duration_days", sa.Integer()),
    )
    op.create_index("ix_crop_rules_crop_family", "crop_rules", ["crop_family"])
    op.create_table(
        "market_prices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("crop_name", sa.String(120), nullable=False),
        sa.Column("mandi_name", sa.String(160), nullable=False),
        sa.Column("modal_price", sa.Numeric(14, 2), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
    )
    for column in ("crop_name", "mandi_name", "date"):
        op.create_index(f"ix_market_prices_{column}", "market_prices", [column])
    op.create_table(
        "plots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("farmer_id", sa.Integer(), sa.ForeignKey("farmers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("area_acres", sa.Numeric(12, 4), nullable=False),
        sa.Column("location", Geometry(geometry_type="GEOMETRY", srid=4326, spatial_index=False)),
        sa.Column("irrigation_type", sa.String(40)),
    )
    op.create_index("ix_plots_farmer_id", "plots", ["farmer_id"])
    op.create_index("idx_plots_location", "plots", ["location"], postgresql_using="gist")
    op.create_table(
        "crop_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("plot_id", sa.Integer(), sa.ForeignKey("plots.id", ondelete="CASCADE"), nullable=False),
        sa.Column("season_id", sa.Integer(), sa.ForeignKey("seasons.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("crop_name", sa.String(120), nullable=False),
        sa.Column("crop_family", sa.String(80)),
        sa.Column("yield_kg", sa.Numeric(14, 3)),
        sa.Column("input_costs", sa.Numeric(14, 2)),
        sa.Column("outcome_notes", sa.Text()),
    )
    op.create_index("ix_crop_records_plot_id", "crop_records", ["plot_id"])
    op.create_index("ix_crop_records_season_id", "crop_records", ["season_id"])
    op.create_table(
        "soil_tests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("plot_id", sa.Integer(), sa.ForeignKey("plots.id", ondelete="CASCADE"), nullable=False),
        sa.Column("n_val", sa.Numeric(10, 3)), sa.Column("p_val", sa.Numeric(10, 3)),
        sa.Column("k_val", sa.Numeric(10, 3)), sa.Column("ph", sa.Numeric(4, 2)),
        sa.Column("organic_matter", sa.Numeric(8, 3)), sa.Column("card_photo_url", sa.String(2048)),
        sa.Column("tested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_soil_tests_plot_id", "soil_tests", ["plot_id"])
    op.create_table(
        "alerts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("farmer_id", sa.Integer(), sa.ForeignKey("farmers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("plot_id", sa.Integer(), sa.ForeignKey("plots.id", ondelete="CASCADE")),
        sa.Column("alert_type", sa.String(64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_alerts_farmer_id", "alerts", ["farmer_id"])
    op.create_index("ix_alerts_plot_id", "alerts", ["plot_id"])


def downgrade() -> None:
    op.drop_table("alerts")
    op.drop_table("soil_tests")
    op.drop_table("crop_records")
    op.drop_index("idx_plots_location", table_name="plots")
    op.drop_table("plots")
    op.drop_table("market_prices")
    op.drop_table("crop_rules")
    op.drop_table("seasons")
    op.drop_table("farmers")
