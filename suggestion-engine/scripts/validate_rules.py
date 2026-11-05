"""Check the knowledge folder: files parse, crop tables are consistent with simulation parameters, review status.

    python scripts/validate_rules.py
Exit code 1 when something is inconsistent. 'Not reviewed' is reported but is not an error.
"""
import sys

from fieldshift.common.config import load_settings
from fieldshift.engine.rules import KnowledgeBase
from fieldshift.simulation.crop_params import load_crop_sim


def main() -> int:
    settings = load_settings()
    kb = KnowledgeBase.load(settings.knowledge_dir)
    sim = load_crop_sim(settings.knowledge_dir)
    problems = []
    for cid, crop in kb.crops.items():
        if cid not in sim:
            problems.append(f"{cid}: no simulation parameters")
            continue
        for season in crop.seasons:
            if season not in sim[cid].sowing:
                problems.append(f"{cid}: no sowing date for season '{season}'")
        if abs(sim[cid].season_days - crop.duration_days) > 15:
            problems.append(f"{cid}: simulated season is {sim[cid].season_days} days but the crop table says {crop.duration_days}")
    for cid in sim:
        if cid not in kb.crops:
            problems.append(f"{cid}: simulation parameters without a crop table entry")
    print(f"{len(kb.crops)} crops, params {kb.params_version}, rules {kb.rules_version}")
    print("agronomist review:", "complete" if kb.reviewed else "NOT reviewed (placeholder values)")
    for p in problems:
        print("PROBLEM:", p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
