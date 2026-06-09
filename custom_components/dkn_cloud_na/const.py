"""Constants for the DKN Cloud NA integration."""

from __future__ import annotations

DOMAIN = "dkn_cloud_na"

CONF_EMAIL = "email"
CONF_PASSWORD = "password"

# Signal fired (per config entry) when fresh device-data arrives over the socket.
SIGNAL_DEVICE_UPDATE = "dkn_cloud_na_device_update_{entry_id}"
