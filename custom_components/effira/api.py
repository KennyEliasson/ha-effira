"""API helpers for the Effira integration."""

from __future__ import annotations

from typing import Any

import requests

from .const import CONF_API_KEY, CONF_KEY_ID, CONF_KEY_SECRET, EFFIRA_BASE, USER_AGENT


def parse_api_key(api_key: str) -> tuple[str, str]:
    """Parse a combined API key string into key id and secret."""
    key_id, separator, key_secret = api_key.partition(":")
    if not separator or not key_id or not key_secret:
        raise ValueError("invalid_api_key_format")
    return key_id.strip(), key_secret.strip()


def get_api_credentials(data: dict[str, Any]) -> tuple[str, str]:
    """Resolve API credentials from either the new or legacy config format."""
    api_key = data.get(CONF_API_KEY)
    if api_key:
        return parse_api_key(api_key)

    key_id = data.get(CONF_KEY_ID)
    key_secret = data.get(CONF_KEY_SECRET)
    if key_id and key_secret:
        return key_id, key_secret

    raise ValueError("missing_api_credentials")


def fetch_access_token_from_credentials(key_id: str, key_secret: str) -> str:
    """Exchange API key credentials for a short-lived access token."""
    response = requests.post(
        f"{EFFIRA_BASE}/api/v1/auth/token",
        auth=(key_id, key_secret),
        headers={"User-Agent": USER_AGENT},
        timeout=10,
    )
    response.raise_for_status()
    return response.json()["access_token"]


def fetch_access_token_from_data(data: dict[str, Any]) -> str:
    """Exchange configured credentials for a short-lived access token."""
    key_id, key_secret = get_api_credentials(data)
    return fetch_access_token_from_credentials(key_id, key_secret)


def fetch_assets(access_token: str) -> list[dict[str, Any]]:
    """Fetch the user's assets."""
    response = requests.get(
        f"{EFFIRA_BASE}/api/v1/assets",
        headers={
            "Authorization": f"Bearer {access_token}",
            "User-Agent": USER_AGENT,
        },
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def format_asset_label(asset: dict[str, Any]) -> str:
    """Build a readable asset label for the selector UI."""
    name = asset.get("name")
    address = asset.get("address") or {}
    address_parts = [
        address.get("address1"),
        address.get("address2"),
        " ".join(part for part in [address.get("zip"), address.get("city")] if part),
    ]
    address_text = ", ".join(part for part in address_parts if part)

    if name and address_text:
        return f"{name} - {address_text}"
    if name:
        return name
    if address_text:
        return address_text
    return asset["assetId"]


def format_entry_title(data: dict[str, Any]) -> str:
    """Build a device title from stored config entry data."""
    asset = {
        "assetId": data.get("asset_id"),
        "name": data.get("asset_name"),
        "address": data.get("address"),
    }
    return format_asset_label(asset)
