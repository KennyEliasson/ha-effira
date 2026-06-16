import os

DOMAIN = "effira"

CONF_API_KEY = "api_key"
CONF_KEY_ID = "key_id"
CONF_KEY_SECRET = "key_secret"
CONF_ASSET_ID = "asset_id"
CONF_ASSET_NAME = "asset_name"
CONF_ADDRESS = "address"
CONF_CLIENT_ID = "client_id"
CONF_SENSOR_ID = "sensor_id"

DEFAULT_EFFIRA_BASE = "https://app.enerflex.cloud"
EFFIRA_BASE = os.environ.get("EFFIRA_BASE", DEFAULT_EFFIRA_BASE).rstrip("/")

ACTION_BOOST = "boost"
ACTION_STOP = "stop"
ACTION_NORMAL = "normal"

SERVICE_BOOST = "boost"
SERVICE_STOP = "stop"
SERVICE_NORMAL = "normal"
SERVICE_CLEAR_PLAN = "clear_plan"
SERVICE_SET_MANUAL_PLAN = "set_manual_plan"
SERVICE_SET_MANUAL_PLAN_FROM_NOW = "set_manual_plan_from_now"
SERVICE_REFRESH = "refresh"

DEFAULT_TIME_ZONE = "Europe/Stockholm"
USER_AGENT = "ha-effira/0.1.1 home-assistant"
