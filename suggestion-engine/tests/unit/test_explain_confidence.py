from fieldshift.engine.confidence import assess
from fieldshift.engine.explain import load_catalog
from fieldshift.store.models import RecommendRequest


def test_confidence_levels():
    assert assess([], [], 3, 0.2).level == "high"
    a = assess(["crop_history", "price:soybean"], [], 3, 0.2)
    assert a.level == "medium" and not a.needs_human_review
    low = assess(["climate_layer", "crop_history"], [], 3, 0.2)
    assert low.level == "low" and low.needs_human_review
    assert assess([], [], 0, None).needs_human_review


def test_every_emitted_code_is_in_the_catalogue(engine, base_request):
    catalog = load_catalog()
    for season, hist in [("kharif-2027", base_request["crop_history"]), ("rabi-2027", [{"season": "kharif-2027", "crop": "soybean"}])]:
        for irrigation in ("rainfed", "full"):
            req = RecommendRequest.model_validate({**base_request, "season": season, "crop_history": hist, "irrigation": irrigation})
            resp = engine.recommend(req)
            for o in resp.options:
                for rc in o.reason_codes + ([o.trade_off_code] if o.trade_off_code else []):
                    assert rc.code in catalog, rc.code
                    assert rc.text_en
            for e in resp.excluded_first_season:
                assert e.code in catalog, e.code


def test_no_options_is_low_confidence_and_reviewed():
    a = assess([], [], 0, None)
    assert a.level == "low" and a.needs_human_review
