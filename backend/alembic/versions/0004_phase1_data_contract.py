"""Complete phase one plot, season, history, and registry data contract."""

from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geometry

revision = "0004_phase1_data_contract"
down_revision = "0003_crop_rule_viability"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Plot area is stored both as the entered local unit and canonical acres.
    op.add_column("plots", sa.Column("area_value", sa.Numeric(12, 4), nullable=True))
    op.add_column("plots", sa.Column("area_unit", sa.String(16), server_default="acre", nullable=False))
    op.add_column("plots", sa.Column("is_archived", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.execute("UPDATE plots SET area_value = area_acres WHERE area_value IS NULL")
    op.alter_column("plots", "area_value", nullable=False)
    op.create_check_constraint("ck_plots_area_acres_positive", "plots", "area_acres > 0")
    op.create_check_constraint("ck_plots_area_value_positive", "plots", "area_value > 0")
    op.create_check_constraint("ck_plots_area_unit", "plots", "area_unit IN ('acre', 'hectare')")
    op.create_check_constraint(
        "ck_plots_location_valid_wgs84", "plots",
        "location IS NULL OR (ST_SRID(location) = 4326 AND GeometryType(location) IN ('POINT', 'POLYGON') AND ST_IsValid(location))",
    )

    # A district/year can have the same season code each year. Legacy rows remain readable.
    op.drop_constraint("seasons_name_key", "seasons", type_="unique")
    op.add_column("seasons", sa.Column("district", sa.String(120), nullable=True))
    op.add_column("seasons", sa.Column("year", sa.Integer(), nullable=True))
    op.add_column("seasons", sa.Column("season_code", sa.String(24), nullable=True))
    op.create_unique_constraint("uq_seasons_district_year_code", "seasons", ["district", "year", "season_code"])

    op.create_unique_constraint(
        "uq_crop_records_plot_season_crop", "crop_records", ["plot_id", "season_id", "crop_name"]
    )

    op.create_table(
        "groups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("district", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_groups_district", "groups", ["district"])

    op.create_table(
        "input_dealers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("district", sa.String(120), nullable=False),
        sa.Column("phone", sa.String(24)),
        sa.Column("certification_source", sa.String(240)),
        sa.Column("certification_valid_until", sa.Date()),
        sa.Column("stock_updated_at", sa.DateTime(timezone=True)),
        sa.Column("location", Geometry(geometry_type="POINT", srid=4326, spatial_index=False)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_input_dealers_district", "input_dealers", ["district"])
    op.create_index("idx_input_dealers_location", "input_dealers", ["location"], postgresql_using="gist")

    op.create_table(
        "warehouses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("district", sa.String(120), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("capacity_tonnes", sa.Numeric(14, 3)),
        sa.Column("commodity", sa.String(120)),
        sa.Column("services", sa.JSON(), nullable=False),
        sa.Column("source", sa.String(240)),
        sa.Column("last_verified_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("latitude BETWEEN -90 AND 90", name="ck_warehouses_latitude"),
        sa.CheckConstraint("longitude BETWEEN -180 AND 180", name="ck_warehouses_longitude"),
    )
    op.create_index("ix_warehouses_district", "warehouses", ["district"])


def downgrade() -> None:
    op.drop_index("ix_warehouses_district", table_name="warehouses")
    op.drop_table("warehouses")
    op.drop_index("idx_input_dealers_location", table_name="input_dealers")
    op.drop_index("ix_input_dealers_district", table_name="input_dealers")
    op.drop_table("input_dealers")
    op.drop_index("ix_groups_district", table_name="groups")
    op.drop_table("groups")
    op.drop_constraint("uq_crop_records_plot_season_crop", "crop_records", type_="unique")
    op.drop_constraint("uq_seasons_district_year_code", "seasons", type_="unique")
    op.drop_column("seasons", "season_code")
    op.drop_column("seasons", "year")
    op.drop_column("seasons", "district")
    op.create_unique_constraint("seasons_name_key", "seasons", ["name"])
    op.drop_constraint("ck_plots_location_valid_wgs84", "plots", type_="check")
    op.drop_constraint("ck_plots_area_unit", "plots", type_="check")
    op.drop_constraint("ck_plots_area_value_positive", "plots", type_="check")
    op.drop_constraint("ck_plots_area_acres_positive", "plots", type_="check")
    op.drop_column("plots", "is_archived")
    op.drop_column("plots", "area_unit")
    op.drop_column("plots", "area_value")
