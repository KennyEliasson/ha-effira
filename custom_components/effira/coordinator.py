"""DataUpdateCoordinator for Effira OPTi.

Responsibilities:
- Auth (API key → access token)
- Verifying connectivity on each poll
- Providing async_action() and async_clear_plan() for HA services to call

Plan logic, price sensors, solar sensors — all belong in HA blueprints/automations,
not here. This coordinator is intentionally thin.

TODO: replace auth verification with a real status GET once Kenny confirms the endpoint.
TODO: replace _submit_action with a direct override endpoint if one exists.
TODO (Kenny): update EFFIRA_BASE to production URL.
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

    def _submit_action(self, asset_id, action):
        """Submit action for the next 15-min slot.

        Uses plan/manual with a single period until we know if a simpler
        immediate-command endpoint exists (pending Kenny's answer).
        """
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
        """Clear manual plan — sends empty periods to return to Effira auto mode.

        Unconfirmed: pending Kenny's answer on whether this is the correct approach.
        """
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

    # ── Service entrypoints (called from __init__.py) ─────────────────────────

    async def async_action(self, action):
        """Submit a single-slot action. Called by effira.boost / stop / normal services."""
        asset_id = self.config_entry.data["asset_id"]
        await self.hass.async_add_executor_job(self._submit_action, asset_id, action)
        self.async_set_updated_data({
            **(self.data or {}),
            "last_action": action,
            "last_action_at": datetime.now(timezone.utc).isoformat(),
        })

    async def async_clear_plan(self):
        """Clear the manual plan. Called by effira.clear_plan service."""
        asset_id = self.config_entry.data["asset_id"]
        await self.hass.async_add_executor_job(self._clear_plan, asset_id)
        self.async_set_updated_data({
            **(self.data or {}),
            "last_action": "auto",
            "last_action_at": datetime.now(timezone.utc).isoformat(),
        })

    # ── Poll ──────────────────────────────────────────────────────────────────

    async def _async_update_data(self):
        """Verify auth works. TODO: replace with status GET once endpoint is known."""
        try:
            await self.hass.async_add_executor_job(self._effira_token)
            return {
                **(self.data or {}),
                "connected": True,
            }
        except Exception as err:
            raise UpdateFailed(f"Effira auth failed: {err}") from err
