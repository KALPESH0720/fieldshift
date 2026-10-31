"""Run the full Alembic chain against the explicitly disposable test database."""

import os
import subprocess
import sys

import pytest
import pytest_asyncio
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

from app.db.base import Base
from app.models import Group, InputDealer, Warehouse  # noqa: F401 - assert registry imports

DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="TEST_DATABASE_URL must point to a disposable PostGIS database")


@pytest.mark.asyncio
async def test_alembic_upgrade_matches_all_model_tables_and_spatial_indexes():
    engine = create_async_engine(DATABASE_URL)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
    await engine.dispose()

    environment = os.environ.copy()
    environment["DATABASE_URL"] = DATABASE_URL
    result = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"],
                            env=environment, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr

    engine = create_async_engine(DATABASE_URL)
    async with engine.connect() as connection:
        tables = await connection.run_sync(lambda sync: set(inspect(sync).get_table_names()) - {"alembic_version", "spatial_ref_sys"})
        plot_indexes = await connection.run_sync(lambda sync: {item["name"] for item in inspect(sync).get_indexes("plots")})
        dealer_indexes = await connection.run_sync(lambda sync: {item["name"] for item in inspect(sync).get_indexes("input_dealers")})
    assert tables == set(Base.metadata.tables)
    assert "idx_plots_location" in plot_indexes
    assert "idx_input_dealers_location" in dealer_indexes

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
    await engine.dispose()
