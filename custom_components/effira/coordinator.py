"""DataUpdateCoordinator for Effira OPTi.

Fetches NordPool prices and solar export from HA, builds a 24h plan,
and submits it to the Effira API every 15 minutes.
"""
import logging
from datetime import datetime, timezone, timedelta

import requests
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN,
    EFFIRA_BASE,
    ACTION_BOOST,
    ACTION_STOP,
    PEAK_MONTHS,
    PEAK_HOUR_START,
    PEAK_HOUR_END,
)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=15)


class EffiraCoordinator(DataUpdateCoordinator):
    """Coordinates fetching data and submitting plans to Effira."""

    def __init__(self, hass, config_entry):
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.config_entry = config_entry
        self._last_status = None
        self._last_plan = []

    # ── Effira auth ───────────────────────────────────────────────────────────

    def _effira_token(self):
        key_id = self.config_entry.data["key_id"]
        key_secret = self.config_entry.data["key_secret"]
        r = requests.post(
            f"{EFFIRA_BASE}/api/v1/auth/token",
            auth=(key_id, key_secret),
            timeout=10,
        )
        r.raise_for_status()
        return r.json()["access_token"]

    # ── Plan logic ────────────────────────────────────────────────────────────

    def _quantize_up(self, dt):
        rem = dt.minute % 15
        if rem == 0 and dt.second == 0 and dt.microsecond == 0:
            return dt
        return (dt + timedelta(minutes=15 - rem)).replace(second=0, microsecond=0)

    def _is_peak_block(self, dt):
        local = dt.astimezone()
        return (
            local.month in PEAK_MONTHS
            and local.weekday() < 5
            and PEAK_HOUR_START <= local.hour < PEAK_HOUR_END
        )

    def _price_for_slot(self, price_map, t):
        hour_start = t.replace(minute=0, second=0, microsecond=0)
        if hour_start in price_map:
            return price_map[hour_start]
        for candidate in sorted(price_map.keys(), reverse=True):
            if candidate <= t:
                return price_map[candidate]
        return None

    def _fmt(self, dt):
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    def _build_plan(self, nordpool_slots, solar_export_w, cheap_price, solar_threshold):
        now = datetime.now(timezone.utc)
        plan_start = self._quantize_up(now)
        end_raw = now + timedelta(hours=24)
        rem = end_raw.minute % 15
        plan_end = (end_raw - timedelta(minutes=rem)).replace(second=0, microsecond=0)
        if plan_end <= plan_start:
            plan_end = plan_start + timedelta(minutes=15)

        price_map = {}
        for slot in nordpool_slots:
            raw = slot.get("start", "").replace("Z", "+00:00")
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
            price = self._price_for_slot(price_map, t)

            if self._is_peak_block(t):
                action = ACTION_STOP
            elif solar_export_w >= solar_threshold:
                action = ACTION_BOOST
            elif price is not None and price <= cheap_price:
                action = ACTION_BOOST
            else:
                action = None

            if action != current_action:
                if current_action is not None and period_start is not None:
                    periods.append({
                        "start": self._fmt(period_start),
                        "end": self._fmt(t),
                        "action": current_action,
                    })
                current_action = action
                period_start = t if action is not None else None

            t = t_next

        if current_action is not None and period_start is not None:
            periods.append({
                "start": self._fmt(period_start),
                "end": self._fmt(plan_end),
                "action": current_action,
            })

        return periods

    # ── HA state helpers ──────────────────────────────────────────────────────

    def _ha_state(self, entity_id):
        state = self.hass.states.get(entity_id)
        if state is None:
            raise UpdateFailed(f"Entity not found: {entity_id}")
        return state

    # ── Main update ───────────────────────────────────────────────────────────

    async def _async_update_data(self):
        data = self.config_entry.data
        nordpool_entity = data.get("nordpool_entity")
        goodwe_entity = data.get("goodwe_entity")
        cheap_price = float(data.get("cheap_price_sek", 1.0))
        solar_threshold = float(data.get("solar_export_w", 300.0))
        asset_id = data["asset_id"]

        try:
            # Read HA states (safe to do in async context)
            np_state = self._ha_state(nordpool_entity)
            attrs = np_state.attributes
            slots = list(attrs.get("raw_today") or []) + list(attrs.get("raw_tomorrow") or [])
            if not slots:
                raise UpdateFailed("No NordPool data in sensor attributes")

            gw_state = self._ha_state(goodwe_entity)
            active_power = float(gw_state.state or 0)
            solar_export = max(0.0, -active_power)

            plan = self._build_plan(slots, solar_export, cheap_price, solar_threshold)

            # Submit plan to Effira (blocking HTTP — run in executor)
            if plan:
                status_code = await self.hass.async_add_executor_job(
                    self._submit_plan, asset_id, plan
                )
            else:
                status_code = None

            self._last_plan = plan
            self._last_status = "ok" if plan else "no_overrides"

            return {
                "solar_export_w": solar_export,
                "current_price": attrs.get("current_price"),
                "slot_count": len(slots),
                "plan": plan,
                "status": self._last_status,
                "submitted_at": datetime.now(timezone.utc).isoformat(),
            }

        except UpdateFailed:
            self._last_status = "error"
            raise
        except Exception as err:
            self._last_status = "error"
            raise UpdateFailed(f"Error updating Effira plan: {err}") from err

    def _submit_plan(self, asset_id, plan):
        token = self._effira_token()
        r = requests.post(
            f"{EFFIRA_BASE}/api/v1/assets/{asset_id}/plan/manual",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={"periods": plan},
            timeout=15,
        )
        r.raise_for_status()
        return r.status_code
