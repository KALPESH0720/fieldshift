"""Secure soil-card workflow, weather snapshots, preferences, and durable alerts."""

from alembic import op
import sqlalchemy as sa

revision = "0008_soil_weather_alerts"
down_revision = "0007_sync_client_timestamps"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("plots", sa.Column("district", sa.String(120), nullable=True))

    op.create_table(
        "soil_card_uploads",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("farmer_id", sa.Integer(), sa.ForeignKey("farmers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("plot_id", sa.Integer(), sa.ForeignKey("plots.id", ondelete="CASCADE"), nullable=False),
        sa.Column("object_key", sa.String(512), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("content_type", sa.String(64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("scan_status", sa.String(24), nullable=False),
        sa.Column("scan_engine", sa.String(120), nullable=False),
        sa.Column("status", sa.String(32), server_default="queued", nullable=False),
        sa.Column("extracted_metrics", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("confidence", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("raw_ocr_metadata", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("ocr_error_code", sa.String(64)),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("object_key", name="uq_soil_card_uploads_object_key"),
        sa.UniqueConstraint("plot_id", "sha256", name="uq_soil_card_upload_plot_sha256"),
    )
    op.create_index("ix_soil_card_uploads_farmer_id", "soil_card_uploads", ["farmer_id"])
    op.create_index("ix_soil_card_uploads_plot_id", "soil_card_uploads", ["plot_id"])
    op.create_index("ix_soil_card_uploads_status", "soil_card_uploads", ["status"])

    op.add_column("soil_tests", sa.Column("nutrient_unit", sa.String(32), server_default="kg/ha", nullable=False))
    op.add_column("soil_tests", sa.Column("organic_matter_unit", sa.String(16), server_default="percent", nullable=False))
    op.add_column("soil_tests", sa.Column("provenance", sa.String(32), server_default="legacy", nullable=False))
    op.add_column("soil_tests", sa.Column("source_reference", sa.String(240)))
    op.add_column("soil_tests", sa.Column("confidence", sa.JSON(), server_default="{}", nullable=False))
    op.add_column("soil_tests", sa.Column("status", sa.String(24), server_default="approved", nullable=False))
    op.add_column("soil_tests", sa.Column("reviewed_by_farmer_id", sa.Integer(), sa.ForeignKey("farmers.id", ondelete="SET NULL")))
    op.add_column("soil_tests", sa.Column("reviewed_at", sa.DateTime(timezone=True)))
    op.add_column("soil_tests", sa.Column("soil_card_upload_id", sa.Integer(), sa.ForeignKey("soil_card_uploads.id", ondelete="SET NULL")))
    op.create_unique_constraint("uq_soil_tests_soil_card_upload_id", "soil_tests", ["soil_card_upload_id"])
    op.create_check_constraint("ck_soil_tests_n_nonnegative", "soil_tests", "n_val IS NULL OR n_val >= 0")
    op.create_check_constraint("ck_soil_tests_p_nonnegative", "soil_tests", "p_val IS NULL OR p_val >= 0")
    op.create_check_constraint("ck_soil_tests_k_nonnegative", "soil_tests", "k_val IS NULL OR k_val >= 0")
    op.create_check_constraint("ck_soil_tests_ph_range", "soil_tests", "ph IS NULL OR ph BETWEEN 0 AND 14")
    op.create_check_constraint("ck_soil_tests_organic_matter_range", "soil_tests", "organic_matter IS NULL OR organic_matter BETWEEN 0 AND 100")

    op.create_table(
        "farmer_preferences",
        sa.Column("farmer_id", sa.Integer(), sa.ForeignKey("farmers.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("weather_alerts_enabled", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("reminders_enabled", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("sms_enabled", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("whatsapp_enabled", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("quiet_hours_start", sa.Time()),
        sa.Column("quiet_hours_end", sa.Time()),
        sa.Column("timezone", sa.String(64), server_default="Asia/Kolkata", nullable=False),
        sa.Column("language", sa.String(16)),
        sa.Column("planned_crops", sa.JSON(), server_default="[]", nullable=False),
    )

    op.create_table(
        "weather_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("farmer_id", sa.Integer(), sa.ForeignKey("farmers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("plot_id", sa.Integer(), sa.ForeignKey("plots.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(80), nullable=False),
        sa.Column("location_key", sa.String(80), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("units", sa.JSON(), nullable=False),
        sa.Column("forecast", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(24), server_default="available", nullable=False),
        sa.Column("error_code", sa.String(64)),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("provider", "location_key", "fetched_at", name="uq_weather_snapshot_provider_location_time"),
    )
    op.create_index("ix_weather_snapshots_farmer_id", "weather_snapshots", ["farmer_id"])
    op.create_index("ix_weather_snapshots_plot_id", "weather_snapshots", ["plot_id"])

    op.add_column("alerts", sa.Column("dedupe_key", sa.String(240)))
    op.create_unique_constraint("uq_alerts_dedupe_key", "alerts", ["dedupe_key"])
    op.add_column("alerts", sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False))
    op.add_column("alerts", sa.Column("next_attempt_at", sa.DateTime(timezone=True)))
    op.add_column("alerts", sa.Column("last_error_code", sa.String(64)))
    op.add_column("alerts", sa.Column("delivery_receipts", sa.JSON(), server_default="{}", nullable=False))
    op.add_column("alerts", sa.Column("dead_lettered_at", sa.DateTime(timezone=True)))
    op.create_index("ix_alerts_next_attempt_at", "alerts", ["next_attempt_at"])


def downgrade() -> None:
    op.drop_index("ix_alerts_next_attempt_at", table_name="alerts")
    op.drop_column("alerts", "dead_lettered_at")
    op.drop_column("alerts", "delivery_receipts")
    op.drop_column("alerts", "last_error_code")
    op.drop_column("alerts", "next_attempt_at")
    op.drop_column("alerts", "attempt_count")
    op.drop_constraint("uq_alerts_dedupe_key", "alerts", type_="unique")
    op.drop_column("alerts", "dedupe_key")
    op.drop_index("ix_weather_snapshots_plot_id", table_name="weather_snapshots")
    op.drop_index("ix_weather_snapshots_farmer_id", table_name="weather_snapshots")
    op.drop_table("weather_snapshots")
    op.drop_table("farmer_preferences")
    op.drop_constraint("ck_soil_tests_organic_matter_range", "soil_tests", type_="check")
    op.drop_constraint("ck_soil_tests_ph_range", "soil_tests", type_="check")
    op.drop_constraint("ck_soil_tests_k_nonnegative", "soil_tests", type_="check")
    op.drop_constraint("ck_soil_tests_p_nonnegative", "soil_tests", type_="check")
    op.drop_constraint("ck_soil_tests_n_nonnegative", "soil_tests", type_="check")
    op.drop_constraint("uq_soil_tests_soil_card_upload_id", "soil_tests", type_="unique")
    op.drop_column("soil_tests", "soil_card_upload_id")
    op.drop_column("soil_tests", "reviewed_at")
    op.drop_column("soil_tests", "reviewed_by_farmer_id")
    op.drop_column("soil_tests", "status")
    op.drop_column("soil_tests", "confidence")
    op.drop_column("soil_tests", "source_reference")
    op.drop_column("soil_tests", "provenance")
    op.drop_column("soil_tests", "organic_matter_unit")
    op.drop_column("soil_tests", "nutrient_unit")
    op.drop_index("ix_soil_card_uploads_status", table_name="soil_card_uploads")
    op.drop_index("ix_soil_card_uploads_plot_id", table_name="soil_card_uploads")
    op.drop_index("ix_soil_card_uploads_farmer_id", table_name="soil_card_uploads")
    op.drop_table("soil_card_uploads")
    op.drop_column("plots", "district")
