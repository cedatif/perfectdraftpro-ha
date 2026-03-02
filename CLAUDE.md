# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Home Assistant custom integration (HACS) for the **PerfectDraft Pro** beer tap. It polls the PerfectDraft cloud API every 60 seconds and exposes machine data as HA entities.

- **HA minimum version**: 2024.1.0
- **IoT class**: `cloud_polling`
- **Platforms**: `sensor` (14 entities) + `binary_sensor` (2 entities)

## Development Workflow

No build system or test suite. To test locally:

1. Symlink or copy `custom_components/perfectdraft_pro/` into your HA `config/custom_components/` directory.
2. Restart Home Assistant.
3. Check logs: **Settings → System → Logs**, or `home-assistant.log`.
4. To reload without full restart: **Settings → Devices & Services → PerfectDraft Pro → 3-dot menu → Reload**.

## Architecture

```
config_flow.py          ← UI wizard (email + password → Cognito auth → stores tokens)
    ↓
__init__.py             ← async_setup_entry: restores session OR authenticates fresh
    ↓
PerfectDraftCoordinator ← DataUpdateCoordinator, polls every 60s
    ↓ (4 parallel requests via asyncio.gather)
perfectdraft_api.py     ← PerfectDraftClient (aiohttp, Cognito auth)
    ↓
sensor.py               ← 14 SensorEntity (all read coordinator.data dict)
binary_sensor.py        ← 2 BinarySensorEntity (door_closed, connected)
```

### Authentication Flow

Auth goes **directly to AWS Cognito** (bypasses PerfectDraft's captcha-protected endpoint):

1. **Initial auth**: `USER_PASSWORD_AUTH` → `AccessToken` (1h) + `RefreshToken` (~30 days)
2. **Token refresh**: `REFRESH_TOKEN_AUTH` every ~55 min, no credentials needed
3. **Refresh token expired**: automatic re-auth with stored email/password
4. Tokens are persisted in `core.config_entries` (encrypted by HA) under keys: `access_token`, `refresh_token`, `token_expiry`, `machine_id`, `device_uuid`

### API Headers

Two header styles are used depending on endpoint:
- `_auth_headers()`: adds `x-api-key` + `x-access-token` (used for most `/api/*` endpoints)
- `_bearer_headers()`: adds `Authorization: Bearer` (used for `/lager-top/*` and `/odp/*` endpoints)

### Coordinator Data Dictionary

`_build_state()` in `__init__.py` assembles the state dict consumed by all entities:

| Key | Source |
|-----|--------|
| `temperature`, `keg_volume`, `keg_pressure`, `last_pour_volume`, `last_pour_duration`, `pours_since_startup`, `error_codes`, `firmware_version`, `door_closed`, `connected` | `GET /api/perfectdraft_machines/{id}` → `details` |
| `target_temperature`, `mode` | `GET /lager-top/machine/{uuid}/settings` → `current` |
| `beer_name`, `keg_inserted_at` | `GET /api/perfectdraft_machines/{id}?groups[]=perfectdraft_keg_active_read` → `kegActive`, then `/api/products/{id}` |
| `loyalty_points`, `tier` | `GET /odp/rewards` |

## Adding a New Sensor

1. Add the key to `const.py` (optional, for documentation).
2. Add a `PerfectDraftSensorDescription` entry to `SENSORS` in `sensor.py`.
3. Populate the key in `_build_state()` in `__init__.py`.

No other files need changing for simple read-only sensors.

## Key Constants (`const.py`)

- `DOMAIN = "perfectdraft_pro"`
- `UPDATE_INTERVAL = 60` (seconds)
- Config/store keys: `CONF_EMAIL`, `CONF_PASSWORD`, `STORE_ACCESS_TOKEN`, `STORE_REFRESH_TOKEN`, `STORE_TOKEN_EXPIRY`, `STORE_MACHINE_ID`, `STORE_DEVICE_UUID`
