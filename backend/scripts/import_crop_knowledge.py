"""Validate and optionally import a pilot crop dataset as draft-only rules."""

import argparse
import asyncio
import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models.crop_rule import CropRule
from config.settings import settings


DEFAULT_DATASET = Path(__file__).resolve().parents[1] / "data" / "pilot" / "mysuru" / "phase0-v1.json"


def read_dataset(path: Path) -> dict:
    dataset = json.loads(path.read_text(encoding="utf-8"))
    if dataset.get("curation_status") != "draft_only" or not dataset.get("crops"):
        raise ValueError("Pilot datasets must contain crops and remain explicitly draft_only")
    for item in dataset["crops"]:
        if not item.get("source_url", "").startswith("https://") or not item.get("source_version"):
            raise ValueError(f"{item.get('crop_name', 'crop')}: source URL and source version are required")
    return dataset


async def import_drafts(dataset: dict) -> tuple[int, int]:
    engine = create_async_engine(settings.database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    inserted = skipped = 0
    try:
        async with sessions() as session:
            for item in dataset["crops"]:
                exists = await session.scalar(select(CropRule.id).where(
                    CropRule.crop_name == item["crop_name"], CropRule.rule_version == 1,
                    CropRule.effective_region == dataset["district"],
                ))
                if exists:
                    skipped += 1
                    continue
                session.add(CropRule(
                    crop_name=item["crop_name"], rule_version=1, schema_version="1.0",
                    crop_family=item.get("crop_family"), source_title=item["source_title"],
                    source_url=item["source_url"], source_version=item["source_version"],
                    effective_region=dataset["district"], effective_seasons=item.get("effective_seasons", []),
                    status="draft", knowledge_data={
                        "pilot_id": dataset["pilot_id"], "pilot_language": dataset["language"],
                        "display_name": item["display_name"], "source_note": item["source_note"],
                        "varieties": item.get("varieties", []),
                        "missing_assumptions": ["yield", "fresh price", "input cost", "fertilizer savings",
                                               "subsidy eligibility", "soil suitability", "water need", "pest risk"],
                    },
                ))
                inserted += 1
            await session.commit()
    finally:
        await engine.dispose()
    return inserted, skipped


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", nargs="?", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--apply", action="store_true", help="insert missing versions into the configured DATABASE_URL as draft-only")
    args = parser.parse_args()
    dataset = read_dataset(args.dataset)
    print(f"Validated pilot {dataset['pilot_id']}: {len(dataset['crops'])} crops; status=draft_only; language={dataset['language']}")
    if not args.apply:
        print("Dry run only. Pass --apply to import draft records into DATABASE_URL.")
        return 0
    inserted, skipped = asyncio.run(import_drafts(dataset))
    print(f"Imported {inserted} draft crop rules; skipped existing versions: {skipped}.")
    print("No rule was activated or published as agronomic advice.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
