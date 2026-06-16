# ha-effira

![Effira OPTi](assets/logo.png)

Community Home Assistant integration for [Effira OPTi](https://effiraenergy.com).

> **Status:** Early beta. This is an unofficial, community-maintained Home Assistant integration and is not affiliated with or officially supported by Effira.

---

## Features

- Config flow with API key and secret
- Asset selection during setup
- Sensors for temperature, online state, planned control, daily consumption and previous hour consumption
- Services for `boost`, `stop`, `normal`, `clear_plan` and `refresh`
- Optional manual plan services for scheduled overrides
- Optional blueprint for price- and solar-driven control

---

## Requirements

- Home Assistant (any recent version)
- Effira OPTi device, claimed in the Effira app
- Effira API key and secret
- *(Optional)* An electricity price sensor — NordPool, Tibber, Amber, etc.
- *(Optional)* A solar/grid power sensor if you want solar-based boosting

---

## Setup

### 1. Create API credentials

Sign in to `https://developers.enerflex.cloud` and create an API key for your asset.

Save the `keyId` and `secret` for Home Assistant setup.

For development against Effira's unstable environment, set `EFFIRA_BASE=https://unstable-app.enerflex.cloud` in the Home Assistant process environment. Default is production: `https://app.enerflex.cloud`.

---

### 2. Install the integration

**Via HACS (recommended):**
1. HACS → Integrations → ⊕ → search "Effira" → Download
2. Restart Home Assistant

**Manually:**
```bash
mkdir -p /config/custom_components/effira
curl -o /config/custom_components/effira/__init__.py \
  https://raw.githubusercontent.com/KennyEliasson/ha-effira/main/custom_components/effira/__init__.py
curl -o /config/custom_components/effira/manifest.json \
  https://raw.githubusercontent.com/KennyEliasson/ha-effira/main/custom_components/effira/manifest.json
curl -o /config/custom_components/effira/const.py \
  https://raw.githubusercontent.com/KennyEliasson/ha-effira/main/custom_components/effira/const.py
curl -o /config/custom_components/effira/coordinator.py \
  https://raw.githubusercontent.com/KennyEliasson/ha-effira/main/custom_components/effira/coordinator.py
curl -o /config/custom_components/effira/config_flow.py \
  https://raw.githubusercontent.com/KennyEliasson/ha-effira/main/custom_components/effira/config_flow.py
curl -o /config/custom_components/effira/sensor.py \
  https://raw.githubusercontent.com/KennyEliasson/ha-effira/main/custom_components/effira/sensor.py
```

Then restart Home Assistant.

---

### 3. Run locally for development

You can run Home Assistant locally in Docker and mount this repository as `/config`:

```bash
docker run --rm -it \
  -p 8123:8123 \
  -v "/Users/kennyeliasson/Code/effira-smart-home-integrations/ha-effira:/config" \
  ghcr.io/home-assistant/home-assistant:stable
```

To develop against Effira's unstable environment, add `EFFIRA_BASE`:

```bash
docker run --rm -it \
  -p 8123:8123 \
  -e EFFIRA_BASE="https://unstable-app.enerflex.cloud" \
  -v "/Users/kennyeliasson/Code/effira-smart-home-integrations/ha-effira:/config" \
  ghcr.io/home-assistant/home-assistant:stable
```

Without `EFFIRA_BASE`, the integration uses production: `https://app.enerflex.cloud`.

---

### 4. Add the integration

**Settings → Devices & Services → Add Integration → Effira OPTi**

Enter your API key and API secret. The integration validates them, fetches your assets, and lets you choose which installation to control.

The integration exposes:
- current planned control with reason, mode and priority
- current temperature
- daily heat pump consumption
- previous hour heat pump consumption

---

### 5. Import the blueprint (optional)

If you want the heat pump to respond automatically to price and solar conditions:

1. **Settings → Automations & Scenes → Blueprints → Import Blueprint**
2. Paste this URL:
   `https://raw.githubusercontent.com/KennyEliasson/ha-effira/main/blueprints/effira_optimize.yaml`
3. Click **Create Automation** and configure:
   - Your electricity price sensor
   - Your price threshold
   - Your solar sensor *(optional)*
   - Capacity tariff peak block *(optional, off by default)*

The automation runs every 15 minutes and calls the appropriate service based on current conditions.

**Logic priority:**
| Priority | Condition | Action |
|---|---|---|
| 1 | Capacity tariff peak hours *(if enabled)* | `effira.stop` |
| 2 | Solar export ≥ threshold *(if solar sensor set)* | `effira.boost` |
| 3 | Price ≤ threshold | `effira.boost` |
| 4 | Default | `effira.clear_plan` *(Effira auto mode)* |

---

## Using the services directly

You can call the services manually from **Developer Tools → Actions**, or use them in scripts and automations:

```yaml
service: effira.boost
```

```yaml
service: effira.stop
```

```yaml
service: effira.clear_plan
```

```yaml
service: effira.refresh
```

---

## Roadmap

- [ ] Direct override endpoint (currently uses plan submission)
- [x] Production environment support
- [ ] HACS default repository listing

---

## License

MIT
