from app.suggestion_engine.filters import CertifiedSeedFilter, RegionFilter, SeasonFilter, WaterFilter
from app.suggestion_engine.pipeline import SuggestionContext


def test_crop_viability_filters_cover_season_region_water_and_seed():
    candidates = [
        {"crop_name": "Chickpea", "suitable_seasons": ["Rabi"],
         "suitable_regions": ["Karnataka"], "water_requirement_mm": 300,
         "certified_seed_available": True},
        {"crop_name": "Rice", "suitable_seasons": ["Kharif"],
         "suitable_regions": ["Punjab"], "water_requirement_mm": 800,
         "certified_seed_available": True},
        {"crop_name": "Millet", "suitable_seasons": ["Rabi"],
         "suitable_regions": ["Karnataka"], "water_requirement_mm": 200,
         "certified_seed_available": False},
    ]
    context = SuggestionContext(plot_id=1, season="Rabi", region="Karnataka", available_water_mm=400)

    kept = SeasonFilter().apply(candidates, context)
    kept = RegionFilter().apply(kept, context)
    kept = WaterFilter().apply(kept, context)
    kept = CertifiedSeedFilter().apply(kept, context)

    assert [candidate["crop_name"] for candidate in kept] == ["Chickpea"]


def test_region_filter_keeps_candidates_without_region_metadata():
    context = SuggestionContext(plot_id=1, season="Kharif", region="Karnataka")
    kept = RegionFilter().apply([{"crop_name": "Unknown-region crop"}], context)
    assert len(kept) == 1
