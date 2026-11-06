import pytest
from fastapi.testclient import TestClient

from fieldshift.api.main import create_app
from fieldshift.common.config import load_settings
from fieldshift.engine.recommend import Engine
from fieldshift.engine.rules import KnowledgeBase
from fieldshift.store.memory_store import MemoryStore

PUNE = {"lat": 18.52, "lon": 73.85}


@pytest.fixture(scope="session")
def settings():
    return load_settings()


@pytest.fixture(scope="session")
def kb(settings):
    return KnowledgeBase.load(settings.knowledge_dir)


@pytest.fixture
def store(settings):
    return MemoryStore.from_cells_file(settings.cells_path)


@pytest.fixture
def engine(kb, store, settings):
    return Engine(kb, store, settings)


@pytest.fixture
def client(engine):
    return TestClient(create_app(engine))


@pytest.fixture
def base_request():
    return {
        "location": PUNE,
        "season": "kharif-2027",
        "irrigation": "rainfed",
        "crop_history": [
            {"season": "rabi-2026", "crop": "wheat"},
            {"season": "kharif-2026", "crop": "maize"},
        ],
        "soil": {"ph": 7.2},
        "prices": [
            {"crop": "soybean", "price": 4800, "source": "msp"},
            {"crop": "pigeonpea", "price": 7500, "source": "msp"},
            {"crop": "maize", "price": 2200, "source": "market"},
            {"crop": "sorghum", "price": 3200, "source": "market"},
            {"crop": "chickpea", "price": 5600, "source": "msp"},
            {"crop": "wheat", "price": 2400, "source": "msp"},
        ],
        "costs": [
            {"crop": "soybean", "cost_per_acre": 12000},
            {"crop": "pigeonpea", "cost_per_acre": 14000},
            {"crop": "maize", "cost_per_acre": 16000},
            {"crop": "sorghum", "cost_per_acre": 9000},
            {"crop": "chickpea", "cost_per_acre": 10000},
            {"crop": "wheat", "cost_per_acre": 13000},
        ],
        "fertilizer_n_price_per_kg": 15,
    }
