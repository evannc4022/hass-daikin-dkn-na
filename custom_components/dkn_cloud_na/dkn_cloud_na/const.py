"""Constants for the DKN Cloud NA (dkncloudna.com) cloud API.

All values are taken verbatim from the decompiled DKN Cloud NA Android app
(Cordova + Vue). See ``decompiled/src-app/src/app.config.js`` and the inlined
production constants in ``app.47f2d272.js``.
"""

from __future__ import annotations

# --- Backend hosts ---------------------------------------------------------
# Production (CONNECT.PROD.API_URL). NOTE: this is NOT dkn.airzonecloud.com,
# which is what the older community integrations target. The North-American
# app uses dkncloudna.com. DEV/PRE only use *.airzonecloud.com:8443.
API_HOST = "https://dkncloudna.com"
API_VERSION = "api/v1"
#: Full REST base, e.g. https://dkncloudna.com/api/v1/
BASE_URL = f"{API_HOST}/{API_VERSION}/"

#: Appended to most REST routes and the per-installation socket namespace.
SCOPE = "dknUsa"

#: Socket.IO engine path (CONNECT.SOCKET_PATH).
SOCKET_PATH = "/api/v1/devices/socket.io/"
#: Socket.IO server base; namespaces are "/users" and "/{installation}::dknUsa".
SOCKET_URL = API_HOST

DEFAULT_TIMEOUT = 10  # seconds (axios.defaults.timeout = 10000)

# --- REST routes (relative to BASE_URL) ------------------------------------
ROUTE_LOGIN = f"auth/login/{SCOPE}"
ROUTE_IS_LOGGED_IN = f"users/isLoggedin/{SCOPE}"
ROUTE_REFRESH = "auth/refreshToken/{refresh_token}/" + SCOPE
ROUTE_LOGOUT = f"users/logout/{SCOPE}"
ROUTE_INSTALLATIONS = f"installations/{SCOPE}"

# --- Socket.IO events ------------------------------------------------------
EVENT_DEVICE_DATA = "device-data"          # inbound: live device state
EVENT_CREATE_MACHINE = "create-machine-event"  # outbound: control a device
EVENT_INSTALLATION_EDITED = "data-installation-edited"

# --- HVAC modes (app.config.js MODES) --------------------------------------
MODE_AUTO = 1
MODE_COOL = 2
MODE_HEAT = 3
MODE_FAN = 4
MODE_DRY = 5

# --- Temperature units (app.config.js UNITS) -------------------------------
UNIT_CELSIUS = 0
UNIT_FAHRENHEIT = 1

# --- Slats (app.config.js SLATS_MODE) --------------------------------------
SLATS_AUTO = 8
SLATS_SWING = 9

# --- Device control property names (mixins/Unit.mixin.js) ------------------
PROP_POWER = "power"
PROP_POWER_ACS = "power_acs"
PROP_POWER_HOT_WATER = "power_hot_water"
PROP_MODE = "mode"
PROP_SPEED = "speed_state"
PROP_SLATS_VERTICAL = "slats_vertical_1"
PROP_SLATS_HORIZONTAL = "slats_horizontal_1"

#: mode -> the setpoint property that mode reads/writes (air units).
SETPOINT_PROP_BY_MODE = {
    MODE_AUTO: "setpoint_air_auto",
    MODE_COOL: "setpoint_air_cool",
    MODE_HEAT: "setpoint_air_heat",
    MODE_FAN: "setpoint_air_vent",
    MODE_DRY: "setpoint_air_dry",
}

#: mode -> the setpoint property for water/Altherma units.
SETPOINT_PROP_BY_MODE_WATER = {
    MODE_AUTO: "setpoint_water_auto",
    MODE_COOL: "setpoint_water_cool",
    MODE_HEAT: "setpoint_water_heat",
}

#: mode -> (min_range_prop, max_range_prop) for air units.
RANGE_PROPS_BY_MODE = {
    MODE_AUTO: ("range_sp_auto_air_min", "range_sp_auto_air_max"),
    MODE_COOL: ("range_sp_cool_air_min", "range_sp_cool_air_max"),
    MODE_HEAT: ("range_sp_hot_air_min", "range_sp_hot_air_max"),
    MODE_DRY: ("range_sp_dry_min", "range_sp_dry_max"),
    MODE_FAN: ("range_sp_vent_min", "range_sp_vent_max"),
}
