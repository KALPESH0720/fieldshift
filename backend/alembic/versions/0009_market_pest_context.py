"""Market price provenance, MSP and reviewed pest host knowledge."""

from alembic import op
import sqlalchemy as sa

revision = "0009_market_pest_context"
down_revision = "0008_soil_weather_alerts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("market_prices", sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.add_column("market_prices", sa.Column("quality_status", sa.String(24), server_default="verified", nullable=False))
    op.add_column("market_prices", sa.Column("mandi_code", sa.String(80)))
    op.add_column("market_prices", sa.Column("commodity_code", sa.String(80)))
    op.add_column("market_prices", sa.Column("arrivals_quantity", sa.Numeric(16, 3)))
    op.add_column("market_prices", sa.Column("arrivals_unit", sa.String(32)))
    op.create_index("ix_market_prices_mandi_code", "market_prices", ["mandi_code"])
    op.create_index("ix_market_prices_commodity_code", "market_prices", ["commodity_code"])
    op.create_index("uq_market_price_feed_record", "market_prices",
                    ["source", "source_version", "district", "mandi_name", "crop_name", "date"], unique=True)
    op.create_table(
        "minimum_support_prices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("crop_name", sa.String(120), nullable=False),
        sa.Column("season", sa.String(80), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(3), server_default="INR", nullable=False),
        sa.Column("price_unit", sa.String(32), server_default="INR/quintal", nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date()),
        sa.Column("source", sa.String(240), nullable=False),
        sa.Column("source_version", sa.String(120), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("crop_name", "season", "year", "source_version", name="uq_msp_crop_season_year_source"),
    )
    op.create_index("ix_minimum_support_prices_crop_name", "minimum_support_prices", ["crop_name"])
    op.create_table(
        "pest_host_rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("target_crop", sa.String(120), nullable=False),
        sa.Column("pest_name", sa.String(160), nullable=False),
        sa.Column("host_crops", sa.JSON(), nullable=False),
        sa.Column("host_families", sa.JSON(), nullable=False),
        sa.Column("effective_region", sa.String(120), nullable=False),
        sa.Column("season", sa.String(80), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("risk_points", sa.Float(), nullable=False),
        sa.Column("source_title", sa.String(240), nullable=False),
        sa.Column("source_url", sa.String(2048), nullable=False),
        sa.Column("source_version", sa.String(120), nullable=False),
        sa.Column("status", sa.String(24), server_default="draft", nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("reviewer_ids", sa.JSON(), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("target_crop", "effective_region", "season", "version", name="uq_pest_host_rule_scope_version"),
    )
    op.create_index("ix_pest_host_rules_target_crop", "pest_host_rules", ["target_crop"])
    op.create_index("ix_pest_host_rules_effective_region", "pest_host_rules", ["effective_region"])


def downgrade() -> None:
    op.drop_table("pest_host_rules")
    op.drop_index("ix_minimum_support_prices_crop_name", table_name="minimum_support_prices")
    op.drop_table("minimum_support_prices")
    op.drop_index("uq_market_price_feed_record", table_name="market_prices")
    op.drop_index("ix_market_prices_commodity_code", table_name="market_prices")
    op.drop_index("ix_market_prices_mandi_code", table_name="market_prices")
    for column in ("arrivals_unit", "arrivals_quantity", "commodity_code", "mandi_code", "quality_status", "fetched_at"):
        op.drop_column("market_prices", column)
