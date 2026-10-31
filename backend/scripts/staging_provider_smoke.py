"""Exercise configured weather and optional messaging providers in staging."""

import argparse
import asyncio
import os

from app.services.integrations.weather_api import WeatherAdapter
from app.services.messaging.sms_gateway import send_sms_message
from app.services.messaging.whatsapp_gateway import send_message
from app.services.weather import normalize_forecast


async def run(args: argparse.Namespace) -> int:
    try:
        raw = await WeatherAdapter(attempts=1).forecast(args.latitude, args.longitude)
        normalized, _ = normalize_forecast(raw)
    except Exception as exc:
        print(f"weather provider: FAIL ({type(exc).__name__})")
        return 1
    print(f"weather provider: OK ({len(normalized['forecast'])} forecast points)")
    if not args.send_test_message:
        print("messaging provider: SKIPPED (use --send-test-message to send one staging message)")
        return 0
    phone = os.getenv("STAGING_SMOKE_PHONE")
    if not phone:
        print("messaging provider: FAIL (STAGING_SMOKE_PHONE is not configured)")
        return 1
    message = "Field Shift staging provider smoke test. No action is required."
    try:
        if args.channel == "sms":
            await send_sms_message(phone, message, attempts=1)
        else:
            await send_message(phone, message, template="staging_smoke", attempts=1)
    except Exception as exc:
        print(f"{args.channel} provider: FAIL ({type(exc).__name__})")
        return 1
    print(f"{args.channel} provider: OK (target omitted)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--latitude", type=float, default=12.9716)
    parser.add_argument("--longitude", type=float, default=77.5946)
    parser.add_argument("--send-test-message", action="store_true",
                        help="send one fixed message only to STAGING_SMOKE_PHONE")
    parser.add_argument("--channel", choices=("sms", "whatsapp"), default="sms")
    args = parser.parse_args()
    if not -90 <= args.latitude <= 90 or not -180 <= args.longitude <= 180:
        parser.error("latitude/longitude are out of bounds")
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
