from __future__ import annotations

from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.post("/optimize", status_code=501)
def optimize():
    """Multi-field optimizer (pipeline P5). Planned for Phase 3; the contract will be added with it."""
    raise HTTPException(status_code=501, detail="multi-field optimizer is planned for Phase 3")
