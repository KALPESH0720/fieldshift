"""Keep distinct AGMARKNET variety/grade rows idempotently."""

from alembic import op
import sqlalchemy as sa


revision = "0011_agmarknet_variety_identity"
down_revision = "0010_agmarknet_record_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("uq_market_price_feed_record", table_name="market_prices")
    op.create_index(
        "uq_market_price_feed_record", "market_prices",
        ["source", "source_version", sa.text("COALESCE(state, '')"),
         sa.text("COALESCE(district, '')"), "mandi_name", "crop_name", "date",
         sa.text("COALESCE(variety, '')"), sa.text("COALESCE(grade, '')")],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_market_price_feed_record", table_name="market_prices")
    op.create_index(
        "uq_market_price_feed_record", "market_prices",
        ["source", "source_version", "district", "mandi_name", "crop_name", "date"], unique=True,
    )
