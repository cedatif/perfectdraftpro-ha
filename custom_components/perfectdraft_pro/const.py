"""Constants for the PerfectDraft Pro integration."""

DOMAIN = "perfectdraft_pro"
PLATFORMS = ["sensor", "binary_sensor"]

# Configuration keys
CONF_EMAIL = "email"
CONF_PASSWORD = "password"

# Stored data keys
STORE_ACCESS_TOKEN = "access_token"
STORE_REFRESH_TOKEN = "refresh_token"
STORE_TOKEN_EXPIRY = "token_expiry"
STORE_MACHINE_ID = "machine_id"
STORE_DEVICE_UUID = "device_uuid"

# Update interval
UPDATE_INTERVAL = 60  # seconds

# Sensor keys — machine details
SENSOR_TEMPERATURE = "temperature"
SENSOR_TARGET_TEMPERATURE = "target_temperature"
SENSOR_KEG_VOLUME = "keg_volume"
SENSOR_KEG_PRESSURE = "keg_pressure"
SENSOR_LAST_POUR_VOLUME = "last_pour_volume"
SENSOR_LAST_POUR_DURATION = "last_pour_duration"
SENSOR_POURS_SINCE_STARTUP = "pours_since_startup"
SENSOR_ERROR_CODES = "error_codes"
SENSOR_FIRMWARE_VERSION = "firmware_version"

# Sensor keys — keg / beer
SENSOR_BEER_NAME = "beer_name"
SENSOR_KEG_INSERTED_AT = "keg_inserted_at"

# Sensor keys — rewards
SENSOR_LOYALTY_POINTS = "loyalty_points"
SENSOR_TIER = "tier"

# Binary sensor keys
BINARY_SENSOR_DOOR = "door_closed"
BINARY_SENSOR_CONNECTED = "connected"
