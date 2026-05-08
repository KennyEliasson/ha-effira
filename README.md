# ha-effira

Home Assistant integration for [Effira OPTi](https://effiraenergy.com) — connects your heat pump to HA and lets you control it with your own price and solar automations.

> **Status:** Early beta. Requires access to Effira's test environment and a manually created API key.
> OAuth login (no API key needed) is planned once the production environment is ready.

---

## How it works

The integration has two parts:

**1. The integration** — handles authentication and exposes the heat pump as an HA device with four services:

| Service | What it does |
|---|---|
| `effira.boost` | Boost the heat pump now |
| `effira.stop` | Stop the heat pump now |
| `effira.normal` | Set to normal mode |
| `effira.clear_plan` | Clear any manual override, return to Effira auto mode |

**2. The blueprint** — an optional automation template that calls those services every 15 minutes based on your electricity price and/or solar export. You point it at whatever sensors you have — NordPool, Tibber, GoodWe, Fronius, anything.

The integration has no built-in opinions about price thresholds, solar thresholds, or tariff zones. All of that lives in your automation.

---

## Prerequisites

- Home Assistant (any recent version)
- Effira OPTi device, claimed in the Effira app
- Effira API key (see setup below)
- *(Optional)* An electricity price sensor — NordPool, Tibber, Amber, etc.
- *(Optional)* A solar/grid power sensor if you want solar-based boosting

---

## Setup

### 1. Get an Effira API key

**a)** Get an authorisation code via [OAuth Debugger](https://oauthdebugger.com):

| Field | Value |
|---|---|
| Authorize URI | `https://easyserv-enduser-unstable.auth.eu-north-1.amazoncognito.com/oauth2/authorize` |
| Client ID | `4fmn375d1uhammpa9j3rld9kum` |
| Redirect URI | `https://oauthdebugger.com/debug` |
| Scope | `enduser/access` |
| Response type | `code` |
| Response mode | `form_post` |

Log in with your Effira account and copy the `code` from the result page.

**b)** Exchange the code for an access token:

```bash
curl -X POST "https://easyserv-enduser-unstable.auth.eu-north-1.amazoncognito.com/oauth2/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=authorization_code&code=<CODE>&client_id=4fmn375d1uhammpa9j3rld9kum&redirect_uri=https://oauthdebugger.com/debug"
```

**c)** Create an API key:

```bash
curl -X POST "https://unstable-app.enerflex.cloud/api/app/v1/me/api-keys" \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"name": "ha-integration", "assetId": "<YOUR_ASSET_ID>"}'
```

Save the `keyId` and `secret` — you'll need them in the next step.

---

### 2. Install the integration

**Via HACS (recommended):**
1. HACS → Integrations → ⊕ → search "Effira" → Download
2. Restart Home Assistant

**Manually:**
```bash
mkdir -p /config/custom_components/effira
curl -o /config/custom_components/effira/__init__.py \
  https://raw.githubusercontent.com/henrikharplinger-arndegothia/ha-effira/main/custom_components/effira/__init__.py
curl -o /config/custom_components/effira/manifest.json \
  https://raw.githubusercontent.com/henrikharplinger-arndegothia/ha-effira/main/custom_components/effira/manifest.json
curl -o /config/custom_components/effira/const.py \
  https://raw.githubusercontent.com/henrikharplinger-arndegothia/ha-effira/main/custom_components/effira/const.py
curl -o /config/custom_components/effira/coordinator.py \
  https://raw.githubusercontent.com/henrikharplinger-arndegothia/ha-effira/main/custom_components/effira/coordinator.py
curl -o /config/custom_components/effira/config_flow.py \
  https://raw.githubusercontent.com/henrikharplinger-arndegothia/ha-effira/main/custom_components/effira/config_flow.py
curl -o /config/custom_components/effira/sensor.py \
  https://raw.githubusercontent.com/henrikharplinger-arndegothia/ha-effira/main/custom_components/effira/sensor.py
```

Then restart Home Assistant.

---

### 3. Add the integration

**Settings → Devices & Services → Add Integration → Effira OPTi**

Enter your Key ID, Key Secret, and Asset ID. HA will create an **Effira OPTi** device with a status sensor showing the current override state (`auto`, `boost`, or `stop`).

---

### 4. Set up the optimization blueprint (optional)

If you want the heat pump to respond automatically to price and solar conditions:

1. **Settings → Automations & Scenes → Blueprints → Import Blueprint**
2. Paste this URL:
   `https://raw.githubusercontent.com/henrikharplinger-arndegothia/ha-effira/main/blueprints/effira_optimize.yaml`
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

You can also call the services manually from **Developer Tools → Services**, or build your own automations:

```yaml
service: effira.boost
```

```yaml
service: effira.stop
```

```yaml
service: effira.clear_plan
```

---

## Roadmap

- [ ] OAuth login flow (no manual API key setup)
- [ ] Status sensor backed by a real API poll endpoint
- [ ] Direct override endpoint (currently uses plan submission)
- [ ] Production environment support
- [ ] HACS default repository listing

---

## License

MIT
