"""DataUpdateCoordinator for Effira OPTi."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
from zoneinfo import ZoneInfo

import requests
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import fetch_access_token_from_data
from .const import (
    CONF_ASSET_ID,
    CONF_ASSET_NAME,
    CONF_CLIENT_ID,
    CONF_SENSOR_ID,
    DEFAULT_TIME_ZONE,
    DOMAIN,
    EFFIRA_BASE,
    USER_AGENT,
)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=10)


class EffiraCoordinator(DataUpdateCoordinator):
    """Coordinate API polling and service actions for one Effira asset."""

    def __init__(self, hass, config_entry):
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.config_entry = config_entry

    @property
    def asset_id(self) -> str:
        return self.config_entry.data[CONF_ASSET_ID]

    @property
    def device_name(self) -> str:
        return self.config_entry.title

    @property
    def client_id(self) -> str | None:
        return self.config_entry.data.get(CONF_CLIENT_ID)

    @property
    def sensor_id(self) -> str | None:
        return self.config_entry.data.get(CONF_SENSOR_ID)

    @property
    def asset_name(self) -> str | None:
        return self.config_entry.data.get(CONF_ASSET_NAME)

    def _effira_token(self):
        return fetch_access_token_from_data(self.config_entry.data)

    def _quantize_up(self, dt):
        rem = dt.minute % 15
        if rem == 0 and dt.second == 0 and dt.microsecond == 0:
            return dt
        return (dt + timedelta(minutes=15 - rem)).replace(second=0, microsecond=0)

    def _fmt(self, dt):
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    def _get(self, token, path):
        response = requests.get(
            f"{EFFIRA_BASE}/api/v1{path}",
            headers={
                "Authorization": f"Bearer {token}",
                "User-Agent": USER_AGENT,
            },
            timeout=10,
        )
        response.raise_for_status()
        return response.json() if response.content else None

    def _get_optional(self, token, path):
        response = requests.get(
            f"{EFFIRA_BASE}/api/v1{path}",
            headers={
                "Authorization": f"Bearer {token}",
                "User-Agent": USER_AGENT,
            },
            timeout=10,
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json() if response.content else None

    def _post_manual_plan(self, asset_id, periods):
        token = self._effira_token()
        response = requests.post(
            f"{EFFIRA_BASE}/api/v1/assets/{asset_id}/plan/manual",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "User-Agent": USER_AGENT,
            },
            json={"periods": periods},
            timeout=15,
        )
        response.raise_for_status()

    def _heatpump_consumption_path(self, asset_id, start, stop, resolution):
        return (
            f"/assets/{asset_id}/heatpumpConsumption"
            f"?start={start}&stop={stop}&resolution={resolution}&timeZone={DEFAULT_TIME_ZONE}"
        )

    def _local_day_range(self):
        now_local = datetime.now(ZoneInfo(DEFAULT_TIME_ZONE))
        start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        return self._fmt(start_local), self._fmt(now_local)

    def _previous_hour_range(self):
        now_local = datetime.now(ZoneInfo(DEFAULT_TIME_ZONE))
        end_local = now_local.replace(minute=0, second=0, microsecond=0)
        start_local = end_local - timedelta(hours=1)
        return self._fmt(start_local), self._fmt(end_local)

    def _extract_consumption_total(self, payload):
        if payload is None:
            return None

        total = payload.get("total") if isinstance(payload, dict) else None
        if isinstance(total, dict) and total.get("consumption") is not None:
            return total.get("consumption")

        data = payload.get("data") if isinstance(payload, dict) else None
        if isinstance(data, dict):
            return data.get("consumption")
        if isinstance(data, list) and data:
            latest_bucket = max(data, key=lambda item: item.get("start", ""))
            return latest_bucket.get("consumption")

        return None

    def _fetch_all(self, asset_id):
        token = self._effira_token()
        day_start, day_stop = self._local_day_range()
        hour_start, hour_stop = self._previous_hour_range()
        status = self._get(token, f"/assets/{asset_id}/currentStatus")
        temp = self._get_optional(token, f"/assets/{asset_id}/tempsensor/latest")
        planned_control = self._get_optional(token, f"/assets/{asset_id}/timeline/now")
        daily_consumption = self._get_optional(
            token,
            self._heatpump_consumption_path(asset_id, day_start, day_stop, "P1D"),
        )
        previous_hour_consumption = self._get_optional(
            token,
            self._heatpump_consumption_path(asset_id, hour_start, hour_stop, "PT1H"),
        )
        return status, temp, planned_control, daily_consumption, previous_hour_consumption

    def _build_period(self, action, start, end):
        if end <= start:
            raise ValueError("End must be later than start.")

        if start < self._quantize_up(datetime.now(timezone.utc)):
            raise ValueError("Start must be in the future and aligned to a 15-minute boundary.")

        if end > datetime.now(timezone.utc) + timedelta(hours=24):
            raise ValueError("End must be within 24 hours from now.")

        if start.minute not in (0, 15, 30, 45) or start.second or start.microsecond:
            raise ValueError("Start must be aligned to a 15-minute boundary.")

        if end.minute not in (0, 15, 30, 45) or end.second or end.microsecond:
            raise ValueError("End must be aligned to a 15-minute boundary.")

        return {"start": self._fmt(start), "end": self._fmt(end), "action": action}

    def _ensure_aware_utc(self, value):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    async def async_action(self, action):
        now = datetime.now(timezone.utc)
        start = self._quantize_up(now)
        end = start + timedelta(minutes=15)
        await self.async_set_manual_plan(action=action, start=start, end=end)

    async def async_set_manual_plan(self, action, start, end):
        start_utc = self._ensure_aware_utc(start)
        end_utc = self._ensure_aware_utc(end)
        period = self._build_period(action, start_utc, end_utc)
        await self.hass.async_add_executor_job(self._post_manual_plan, self.asset_id, [period])
        await self.async_request_refresh()

    async def async_set_manual_plan_from_now(self, action, duration_minutes):
        if duration_minutes % 15 != 0:
            raise ValueError("Duration must be divisible by 15 minutes.")

        now = datetime.now(timezone.utc)
        start = self._quantize_up(now)
        end = start + timedelta(minutes=duration_minutes)
        await self.async_set_manual_plan(action=action, start=start, end=end)

    async def async_clear_plan(self):
        await self.hass.async_add_executor_job(self._post_manual_plan, self.asset_id, [])
        await self.async_request_refresh()

    async def _async_update_data(self):
        try:
            status, temp, planned_control, daily_consumption, previous_hour_consumption = (
                await self.hass.async_add_executor_job(self._fetch_all, self.asset_id)
            )

            online = None
            last_action = None
            last_action_source = None
            if status:
                online = (status.get("online") or {}).get("value")
                action_obj = status.get("lastAction") or {}
                last_action = action_obj.get("state")
                last_action_source = (action_obj.get("prio") or {}).get("type")

            planned_state = None
            planned_reason = None
            planned_mode = None
            planned_priority = None
            if planned_control:
                planned_state = planned_control.get("state")
                planned_reason = planned_control.get("reason")
                planned_mode = planned_control.get("mode")
                planned_priority = planned_control.get("priority")

            return {
                "connected": True,
                "online": online,
                "last_action": last_action,
                "last_action_source": last_action_source,
                "temp": temp.get("temperature") if temp else None,
                "planned_state": planned_state,
                "planned_reason": planned_reason,
                "planned_mode": planned_mode,
                "planned_priority": planned_priority,
                "daily_heatpump_consumption": self._extract_consumption_total(daily_consumption),
                "previous_hour_heatpump_consumption": self._extract_consumption_total(
                    previous_hour_consumption
                ),
            }
        except Exception as err:
            raise UpdateFailed(f"Effira API error: {err}") from err
