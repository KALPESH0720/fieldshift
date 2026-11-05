"""Connectivity and assumption checks for the live services. Run on a machine that has internet access.

Each check returns (name, ok, detail). Nothing here changes any data. The development sandbox had no
access to these services, so these checks are how the adapters get verified for the first time.
"""
from __future__ import annotations

import os
import uuid
from datetime import date
from typing import Callable, Optional

from ..common.http import HttpClient
from .appeears import AppeearsClient
from .modis import PRODUCT as MODIS_PRODUCT
from .power import PowerClient
from .smap import PRODUCT as SMAP_PRODUCT

Check = tuple[str, bool, str]


def check_power(http: Optional[HttpClient] = None) -> Check:
    try:
        s = PowerClient(http=http).fetch("check", 18.55, 73.85, date(2020, 6, 1), date(2020, 6, 10))
        valid = sum(1 for v in s.rain if v is not None)
        return "NASA POWER daily point", len(s) == 10 and valid > 0, f"{len(s)} days, {valid} with rain values"
    except Exception as e:
        return "NASA POWER daily point", False, f"{type(e).__name__}: {e}"


def check_appeears(username: Optional[str], password: Optional[str], http: Optional[HttpClient] = None) -> list[Check]:
    if not username or not password:
        return [("AppEEARS login", False, "set EARTHDATA_USERNAME and EARTHDATA_PASSWORD")]
    client = AppeearsClient(http=http)
    try:
        client.login(username, password)
    except Exception as e:
        return [("AppEEARS login", False, f"{type(e).__name__}: {e}")]
    out: list[Check] = [("AppEEARS login", True, "token received")]
    try:
        products = client.http.get_json(f"{client.base_url}/product", headers=client._headers())
        names = {p.get("ProductAndVersion") for p in products}
        for label, product in (("SMAP L4 product", SMAP_PRODUCT), ("MODIS NDVI product", MODIS_PRODUCT)):
            if product in names:
                out.append((label, True, f"{product} is listed"))
            else:
                family = product.split(".")[0]
                alternatives = sorted(n for n in names if n and n.startswith(family))
                out.append((label, False, f"{product} not listed; available versions: {alternatives or 'none'}"))
    except Exception as e:
        out.append(("AppEEARS product list", False, f"{type(e).__name__}: {e}"))
    return out


def check_gcs(bucket: Optional[str]) -> Check:
    if not bucket:
        return "Cloud Storage read/write", False, "pass --bucket gs://YOUR_BUCKET"
    from ..common import io
    path = f"{bucket.rstrip('/')}/_check/{uuid.uuid4().hex}.json"
    try:
        io.write_json(path, {"ok": True})
        ok = io.read_json(path) == {"ok": True}
        return "Cloud Storage read/write", ok, f"wrote and read {path} (delete it afterwards)"
    except Exception as e:
        return "Cloud Storage read/write", False, f"{type(e).__name__}: {e}"


def run_checks(bucket: Optional[str] = None, env: Optional[dict] = None, skip: tuple[str, ...] = ()) -> list[Check]:
    env = env if env is not None else dict(os.environ)
    results: list[Check] = []
    steps: list[tuple[str, Callable[[], list[Check]]]] = [
        ("power", lambda: [check_power()]),
        ("appeears", lambda: check_appeears(env.get("EARTHDATA_USERNAME"), env.get("EARTHDATA_PASSWORD"))),
        ("gcs", lambda: [check_gcs(bucket)]),
    ]
    for key, fn in steps:
        if key not in skip:
            results += fn()
    return results
