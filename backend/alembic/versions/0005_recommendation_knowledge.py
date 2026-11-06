"""Versioned recommendation knowledge, review workflow, and reproducible outcomes."""

from alembic import op
import sqlalchemy as sa

revision = "0005_recommendation_knowledge"
down_revision = "0004_phase1_data_contract"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("crop_rules_crop_name_key", "crop_rules", type_="unique")
    op.add_column("crop_rules", sa.Column("rule_version", sa.Integer(), server_default="1", nullable=False))
    op.add_column("crop_rules", sa.Column("schema_version", sa.String(24), server_default="1.0", nullable=False))
    op.add_column("crop_rules", sa.Column("source_title", sa.String(240)))
    op.add_column("crop_rules", sa.Column("source_url", sa.String(2048)))
    op.add_column("crop_rules", sa.Column("source_version", sa.String(120)))
    op.add_column("crop_rules", sa.Column("effective_region", sa.String(120)))
    op.add_column("crop_rules", sa.Column("effective_seasons", sa.JSON()))
    op.add_column("crop_rules", sa.Column("knowledge_data", sa.JSON()))
    op.add_column("crop_rules", sa.Column("status", sa.String(24), server_default="draft", nullable=False))
    op.add_column("crop_rules", sa.Column("approved_at", sa.DateTime(timezone=True)))
    op.add_column("crop_rules", sa.Column("activated_at", sa.DateTime(timezone=True)))
    op.create_unique_constraint("uq_crop_rules_region_version", "crop_rules", ["crop_name", "effective_region", "rule_version"])

    op.add_column("soil_tests", sa.Column("soil_type", sa.String(80)))
    op.add_column("market_prices", sa.Column("district", sa.String(120)))
    op.add_column("market_prices", sa.Column("source", sa.String(240)))
    op.add_column("market_prices", sa.Column("source_version", sa.String(120)))
    op.add_column("market_prices", sa.Column("currency", sa.String(3), server_default="INR", nullable=False))
    op.add_column("market_prices", sa.Column("price_unit", sa.String(32), server_default="unknown", nullable=False))
    op.add_column("market_prices", sa.Column("reported_unit", sa.String(64)))
    op.create_index("ix_market_prices_district", "market_prices", ["district"])

    op.create_table(
        "crop_rule_reviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("crop_rule_id", sa.Integer(), sa.ForeignKey("crop_rules.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reviewer_id", sa.String(160), nullable=False),
        sa.Column("decision", sa.String(16), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("crop_rule_id", "reviewer_id", name="uq_crop_rule_reviews_reviewer"),
    )
    op.create_index("ix_crop_rule_reviews_crop_rule_id", "crop_rule_reviews", ["crop_rule_id"])
    op.create_table(
        "crop_rule_audits",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("crop_rule_id", sa.Integer(), sa.ForeignKey("crop_rules.id", ondelete="CASCADE"), nullable=False),
        sa.Column("actor_id", sa.String(160), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_crop_rule_audits_crop_rule_id", "crop_rule_audits", ["crop_rule_id"])

    op.create_table(
        "recommendation_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("farmer_id", sa.Integer(), sa.ForeignKey("farmers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("plot_id", sa.Integer(), sa.ForeignKey("plots.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ruleset_version", sa.String(64), nullable=False),
        sa.Column("scorer_version", sa.String(64), nullable=False),
        sa.Column("request_snapshot", sa.JSON(), nullable=False),
        sa.Column("rule_snapshot", sa.JSON(), nullable=False),
        sa.Column("response_snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_recommendation_runs_farmer_id", "recommendation_runs", ["farmer_id"])
    op.create_index("ix_recommendation_runs_plot_id", "recommendation_runs", ["plot_id"])
    op.create_table(
        "recommendation_outcomes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("recommendation_id", sa.Integer(), sa.ForeignKey("recommendation_runs.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("planted_crop", sa.String(120), nullable=False),
        sa.Column("actual_yield_kg", sa.Numeric(14, 3)),
        sa.Column("actual_input_cost", sa.Numeric(14, 2)),
        sa.Column("currency", sa.String(3), server_default="INR", nullable=False),
        sa.Column("outcome_notes", sa.Text()),
        sa.Column("observed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("recommendation_outcomes")
    op.drop_index("ix_recommendation_runs_plot_id", table_name="recommendation_runs")
    op.drop_index("ix_recommendation_runs_farmer_id", table_name="recommendation_runs")
    op.drop_table("recommendation_runs")
    op.drop_index("ix_crop_rule_audits_crop_rule_id", table_name="crop_rule_audits")
    op.drop_table("crop_rule_audits")
    op.drop_index("ix_crop_rule_reviews_crop_rule_id", table_name="crop_rule_reviews")
    op.drop_table("crop_rule_reviews")
    op.drop_index("ix_market_prices_district", table_name="market_prices")
    op.drop_column("market_prices", "price_unit")
    op.drop_column("market_prices", "reported_unit")
    op.drop_column("market_prices", "currency")
    op.drop_column("market_prices", "source_version")
    op.drop_column("market_prices", "source")
    op.drop_column("market_prices", "district")
    op.drop_column("soil_tests", "soil_type")
    op.drop_constraint("uq_crop_rules_region_version", "crop_rules", type_="unique")
    op.drop_column("crop_rules", "activated_at")
    op.drop_column("crop_rules", "approved_at")
    op.drop_column("crop_rules", "status")
    op.drop_column("crop_rules", "knowledge_data")
    op.drop_column("crop_rules", "effective_seasons")
    op.drop_column("crop_rules", "effective_region")
    op.drop_column("crop_rules", "source_version")
    op.drop_column("crop_rules", "source_url")
    op.drop_column("crop_rules", "source_title")
    op.drop_column("crop_rules", "schema_version")
    op.drop_column("crop_rules", "rule_version")
    op.create_unique_constraint("crop_rules_crop_name_key", "crop_rules", ["crop_name"])
