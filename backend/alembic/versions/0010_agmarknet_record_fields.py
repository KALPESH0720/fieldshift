"""Persist AGMARKNET state, variety, grade, and price range fields."""

from alembic import op
import sqlalchemy as sa


revision = "0010_agmarknet_record_fields"
down_revision = "0009_market_pest_context"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("market_prices", sa.Column("state", sa.String(120)))
    op.add_column("market_prices", sa.Column("variety", sa.String(160)))
    op.add_column("market_prices", sa.Column("grade", sa.String(80)))
    op.add_column("market_prices", sa.Column("min_price", sa.Numeric(14, 2)))
    op.add_column("market_prices", sa.Column("max_price", sa.Numeric(14, 2)))
    op.add_column("market_prices", sa.Column("reported_min_price", sa.Numeric(14, 2)))
    op.add_column("market_prices", sa.Column("reported_max_price", sa.Numeric(14, 2)))


def downgrade() -> None:
    for column in ("reported_max_price", "reported_min_price", "max_price", "min_price", "grade", "variety", "state"):
        op.drop_column("market_prices", column)
