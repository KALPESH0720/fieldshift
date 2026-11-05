import httpx

from fieldshift.common.http import HttpClient
from fieldshift.data.live_check import check_appeears, check_gcs, check_power, run_checks
from fieldshift.data.modis import PRODUCT as MODIS
from fieldshift.data.smap import PRODUCT as SMAP


def _http(handler):
    return HttpClient(transport=httpx.MockTransport(handler), retries=0, sleep=lambda s: None)


def _power_ok(req):
    keys = [f"202006{d:02d}" for d in range(1, 11)]
    col = lambda v: {k: v for k in keys}  # noqa: E731
    return httpx.Response(200, json={"properties": {"parameter": {
        "T2M_MAX": col(31.0), "T2M_MIN": col(21.0), "PRECTOTCORR": col(4.0), "ALLSKY_SFC_SW_DWN": col(15.0)}}})


def test_power_check_passes_and_fails_cleanly():
    name, ok, detail = check_power(_http(_power_ok))
    assert ok and "10 days" in detail
    _, ok, detail = check_power(_http(lambda req: httpx.Response(500)))
    assert not ok and "HttpError" in detail


def _appeears_handler(products, login_ok=True):
    def handler(req):
        if req.url.path.endswith("/login"):
            return httpx.Response(200, json={"token": "t"}) if login_ok else httpx.Response(401, text="bad credentials")
        if req.url.path.endswith("/product"):
            return httpx.Response(200, json=[{"ProductAndVersion": p} for p in products])
        return httpx.Response(404)
    return handler


def test_appeears_check_reports_missing_credentials_and_bad_login():
    assert check_appeears(None, None)[0][1] is False
    results = check_appeears("u", "p", _http(_appeears_handler([], login_ok=False)))
    assert results == [("AppEEARS login", False, results[0][2])] and "401" in results[0][2]


def test_appeears_check_verifies_product_versions_and_suggests_alternatives():
    good = check_appeears("u", "p", _http(_appeears_handler([SMAP, MODIS])))
    assert [ok for _, ok, _ in good] == [True, True, True]
    stale = check_appeears("u", "p", _http(_appeears_handler(["SPL4SMGP.007", MODIS])))
    smap = next(r for r in stale if r[0] == "SMAP L4 product")
    assert smap[1] is False and "SPL4SMGP.007" in smap[2]


def test_gcs_check_needs_a_bucket_and_run_checks_can_skip():
    assert check_gcs(None)[1] is False
    results = run_checks(bucket=None, env={}, skip=("power", "appeears"))
    assert [r[0] for r in results] == ["Cloud Storage read/write"]
