"""DataUpdateCoordinator for Effira OPTi.

Polls currentStatus, referencetemperature and plan/manual every 5 minutes.
Provides async_action() and async_clear_plan() for HA services to call.
"""
import logging
from datetime import datetime, timezone, timedelta

import requests
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, EFFIRA_BASE

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=5)


class EffiraCoordinator(DataUpdateCoordinator):

    def __init__(self, hass, config_entry):
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.config_entry = config_entry

    # ── Auth ──────────────────────────────────────────────────────────────────

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

    # ── Time helpers ──────────────────────────────────────────────────────────

    def _quantize_up(self, dt):
        rem = dt.minute % 15
        if rem == 0 and dt.second == 0 and dt.microsecond == 0:
            return dt
        return (dt + timedelta(minutes=15 - rem)).replace(second=0, microsecond=0)

    def _fmt(self, dt):
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    # ── API calls ─────────────────────────────────────────────────────────────

    def _get(self, token, path):
        r = requests.get(
            f"{EFFIRA_BASE}/api/v1{path}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        r.raise_for_status()
        return r.json() if r.content else None

    def _fetch_all(self, asset_id):
        token = self._effira_token()
        status = self._get(token, f"/assets/{asset_id}/currentStatus")
        ref_temp = self._get(token, f"/assets/{asset_id}/referencetemperature")
        manual_plan = self._get(token, f"/assets/{asset_id}/plan/manual")
        return status, ref_temp, manual_plan

    def _submit_action(self, asset_id, action):
        token = self._effira_token()
        now = datetime.now(timezone.utc)
        start = self._quantize_up(now)
        end = start + timedelta(minutes=15)
        r = requests.post(
            f"{EFFIRA_BASE}/api/v1/assets/{asset_id}/plan/manual",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={"periods": [{"start": self._fmt(start), "end": self._fmt(end), "action": action}]},
            timeout=15,
        )
        r.raise_for_status()

    def _clear_plan(self, asset_id):
        token = self._effira_token()
        r = requests.post(
            f"{EFFIRA_BASE}/api/v1/assets/{asset_id}/plan/manual",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={"periods": []},
            timeout=15,
        )
        r.raise_for_status()

    # ── Service entrypoints ───────────────────────────────────────────────────

    async def async_action(self, action):
        asset_id = self.config_entry.data["asset_id"]
        await self.hass.async_add_executor_job(self._submit_action, asset_id, action)
        self.async_set_updated_data({
            **(self.data or {}),
            "manual_action": action,
            "last_action_at": datetime.now(timezone.utc).isoformat(),
        })

    async def async_clear_plan(self):
        asset_id = self.config_entry.data["asset_id"]
        await self.hass.async_add_executor_job(self._clear_plan, asset_id)
        self.async_set_updated_data({
            **(self.data or {}),
            "manual_action": None,
            "last_action_at": datetime.now(timezone.utc).isoformat(),
        })

    # ── Poll ──────────────────────────────────────────────────────────────────

    async def _async_update_data(self):
        asset_id = self.config_entry.data["asset_id"]
        try:
            status, ref_temp, manual_plan = await self.hass.async_add_executor_job(
                self._fetch_all, asset_id
            )

            online = None
            last_action = None
            last_action_source = None
            if status:
                online_obj = status.get("online") or {}
                online = online_obj.get("value")
                action_obj = status.get("lastAction") or {}
                last_action = action_obj.get("state")
                prio = action_obj.get("prio") or {}
                last_action_source = prio.get("type")

            ref_temp_value = None
            if ref_temp:
                ref_temp_value = ref_temp.get("value")

            active_periods = []
            if manual_plan:
                active_periods = manual_plan.get("rawPeriods") or []

            return {
                "connected": True,
                "online": online,
                "last_action": last_action,
                "last_action_source": last_action_source,
                "ref_temp": ref_temp_value,
                "active_periods": active_periods,
                "manual_action": (self.data or {}).get("manual_action"),
                "last_action_at": (self.data or {}).get("last_action_at"),
            }

        except Exception as err:
            raise UpdateFailed(f"Effira API error: {err}") from err
