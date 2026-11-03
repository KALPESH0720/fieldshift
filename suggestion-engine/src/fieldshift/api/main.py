"""FastAPI app. Run with: uvicorn fieldshift.api.main:app --reload"""
from __future__ import annotations

from typing import Optional

from fastapi import Depends, FastAPI

from ..common.config import Settings, load_pipeline_settings, load_settings
from ..common.versions import MODEL_VERSION
from ..engine.recommend import Engine
from ..engine.rules import KnowledgeBase
from ..store.memory_store import MemoryStore
from ..simulation.launcher import build_launcher
from . import (routes_actions, routes_alerts, routes_indicators, routes_jobs, routes_optimize, routes_recommend,
               routes_rescore)
from .deps import require_api_key


def create_app(engine: Optional[Engine] = None, settings: Optional[Settings] = None) -> FastAPI:
    if engine is None:
        settings = settings or load_settings()
        kb = KnowledgeBase.load(settings.knowledge_dir)
        store = MemoryStore.from_cells_file(settings.cells_path)
        engine = Engine(kb, store, settings, launcher=build_launcher(settings, load_pipeline_settings(), store))

    app = FastAPI(title="Field Shift suggestion engine", version=MODEL_VERSION)
    app.state.engine = engine

    @app.get("/v1/health")
    def health():
        e = app.state.engine
        return {
            "status": "ok",
            "model": MODEL_VERSION,
            "rules": e.kb.rules_version,
            "params": e.kb.params_version,
            "knowledge_reviewed": e.kb.reviewed,
        }

    guard = [Depends(require_api_key)]
    for module in (routes_recommend, routes_rescore, routes_jobs, routes_alerts, routes_actions, routes_optimize,
                   routes_indicators):
        app.include_router(module.router, prefix="/v1", dependencies=guard)
    return app


app = create_app()
