#!/usr/bin/env python3
"""
Effira OPTi — Home Assistant bridge
====================================
Reads NordPool 15-min prices and current solar export from HA,
computes a 24-hour heat-pump plan, authenticates with the Effira
customer API, and submits the plan.

Run every 15 minutes via HA shell_command (see automations/effira_heat_pump.yaml).
Credentials are read from a .env file alongside this script (see config.env.example).

Action priority per 15-min slot
--------------------------------
1. Peak tariff block (Nov-Mar, weekday 07-19) -> "stop"
   Molndal capacity tariff: avoid adding load during these hours.
2. Solar export >= threshold                   -> "boost"
   Use free solar surplus to pre-heat house / hot water.
3. Cheap price (<= threshold)                  -> "boost"
   Pre-heat when electricity is inexpensive.
4. Default                                     -> omit slot
   Effira's automatic optimisation handles the rest.

Action names from Effira OpenAPI spec (ManualPlanAction enum): "boost", "stop", "normal".
"""

import os
import sys
import requests
from datetime import datetime, timezone, timedelta
from pathlib import Path


def _load_env():
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


_load_env()

EFFIRA_KEY_ID     = os.environ["EFFIRA_KEY_ID"]
EFFIRA_KEY_SECRET = os.environ["EFFIRA_KEY_SECRET"]
EFFIRA_ASSET_ID   = os.environ.get("EFFIRA_ASSET_ID", "69fc584c69510b39091a2b02")
EFFIRA_BASE       = "https://unstable-app.enerflex.cloud"

HA_URL   = os.environ.get("HA_URL", "http://homeassistant.local:8123")
HA_TOKEN = os.environ["HA_TOKEN"]

NORDPOOL_ENTITY = os.environ.get("NORDPOOL_ENTITY", "sensor.nordpool_kwh_se3_sek_3_10_025")
GOODWE_ENTITY   = os.environ.get("GOODWE_ENTITY", "sensor.goodwe_active_power")

CHEAP_PRICE_SEK = float(os.environ.get("CHEAP_PRICE_SEK", "1.0"))
SOLAR_EXPORT_W  = float(os.environ.get("SOLAR_EXPORT_W",  "300"))

ACTION_BOOST  = "boost"
ACTION_STOP   = "stop"

PEAK_MONTHS     = {11, 12, 1, 2, 3}
PEAK_HOUR_START = 7
PEAK_HOUR_END   = 19


def ha_state(entity_id):
    r = requests.get(
        f"{HA_URL}/api/states/{entity_id}",
        headers={"Authorization": f"Bearer {HA_TOKEN}"},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()


def effira_token():
    r = requests.post(
        f"{EFFIRA_BASE}/api/v1/auth/token",
        auth=(EFFIRA_KEY_ID, EFFIRA_KEY_SECRET),
        timeout=10,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def _quantize_up(dt):
    rem = dt.minute % 15
    if rem == 0 and dt.second == 0 and dt.microsecond == 0:
        return dt
    return (dt + timedelta(minutes=15 - rem)).replace(second=0, microsecond=0)


def _is_peak_block(dt):
    local = dt.astimezone()
    return (
        local.month in PEAK_MONTHS
        and local.weekday() < 5
        and PEAK_HOUR_START <= local.hour < PEAK_HOUR_END
    )


def _price_for_slot(price_map, t):
    hour_start = t.replace(minute=0, second=0, microsecond=0)
    if hour_start in price_map:
        return price_map[hour_start]
    for candidate in sorted(price_map.keys(), reverse=True):
        if candidate <= t:
            return price_map[candidate]
    return None


def _fmt(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def build_plan(nordpool_slots, solar_export_w):
    now = datetime.now(timezone.utc)
    plan_start = _quantize_up(now)
    end_raw = now + timedelta(hours=24)
    rem = end_raw.minute % 15
    plan_end = (end_raw - timedelta(minutes=rem)).replace(second=0, microsecond=0)
    if plan_end <= plan_start:
        plan_end = plan_start + timedelta(minutes=15)

    price_map = {}
    for slot in nordpool_slots:
        raw = slot.get("start", "")
        if not raw:
            continue
        raw = raw.replace("Z", "+00:00")
        try:
            ts = datetime.fromisoformat(raw)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            price_map[ts.astimezone(timezone.utc)] = float(slot["value"])
        except (ValueError, KeyError):
            continue

    periods = []
    current_action = None
    period_start = None

    t = plan_start
    while t < plan_end:
        t_next = t + timedelta(minutes=15)
        price = _price_for_slot(price_map, t)

        if _is_peak_block(t):
            action = ACTION_STOP
        elif solar_export_w >= SOLAR_EXPORT_W:
            action = ACTION_BOOST
        elif price is not None and price <= CHEAP_PRICE_SEK:
            action = ACTION_BOOST
        else:
            action = None

        if action != current_action:
            if current_action is not None and period_start is not None:
                periods.append({
                    "start":  _fmt(period_start),
                    "end":    _fmt(t),
                    "action": current_action,
                })
            current_action = action
            period_start = t if action is not None else None

        t = t_next

    if current_action is not None and period_start is not None:
        periods.append({
            "start":  _fmt(period_start),
            "end":    _fmt(plan_end),
            "action": current_action,
        })

    return periods


def main():
    np_state = ha_state(NORDPOOL_ENTITY)
    attrs    = np_state.get("attributes", {})
    slots    = (attrs.get("raw_today") or []) + (attrs.get("raw_tomorrow") or [])

    if not slots:
        print("ERROR: No NordPool data in sensor attributes.", file=sys.stderr)
        sys.exit(1)

    gw_state     = ha_state(GOODWE_ENTITY)
    active_power = float(gw_state.get("state") or 0)
    solar_export = max(0.0, -active_power)

    print(f"Solar: {solar_export:.0f}W | Slots: {len(slots)} | Price: {attrs.get('current_price', '?')} SEK/kWh")

    plan = build_plan(slots, solar_export)

    if not plan:
        print("No overrides needed -- Effira auto logic handles everything.")
        return

    print(f"Plan: {len(plan)} period(s)")
    for p in plan:
        print(f"  {p['start']} -> {p['end']} [{p['action']}]")

    token = effira_token()

    r = requests.post(
        f"{EFFIRA_BASE}/api/v1/assets/{EFFIRA_ASSET_ID}/plan/manual",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type":  "application/json",
        },
        json={"periods": plan},
        timeout=15,
    )

    print(f"Effira API: {r.status_code}")
    if not r.ok:
        print(r.text, file=sys.stderr)
        sys.exit(1)

    print("Plan submitted successfully.")


if __name__ == "__main__":
    main()
