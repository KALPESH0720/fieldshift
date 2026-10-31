"""Add crop region, season, and certified-seed suitability metadata."""

from alembic import op
import sqlalchemy as sa

revision = "0003_crop_rule_viability"
down_revision = "0002_sync_delta"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("crop_rules", sa.Column("suitable_seasons", sa.JSON(), nullable=True))
    op.add_column("crop_rules", sa.Column("suitable_regions", sa.JSON(), nullable=True))
    op.add_column("crop_rules", sa.Column("certified_seed_available", sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column("crop_rules", "certified_seed_available")
    op.drop_column("crop_rules", "suitable_regions")
    op.drop_column("crop_rules", "suitable_seasons")
