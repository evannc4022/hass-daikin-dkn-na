"""Config flow for DKN Cloud NA."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .dkn_cloud_na import DknApiError, DknAuthError, DknCloudNaClient, DknConnectionError

from .const import CONF_EMAIL, CONF_PASSWORD, DOMAIN

STEP_USER_SCHEMA = vol.Schema(
    {vol.Required(CONF_EMAIL): str, vol.Required(CONF_PASSWORD): str}
)


class DknConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the email/password login flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            email = user_input[CONF_EMAIL].strip()
            await self.async_set_unique_id(email.lower())
            self._abort_if_unique_id_configured()

            session = async_get_clientsession(self.hass)
            client = DknCloudNaClient(session)
            try:
                await client.login(email, user_input[CONF_PASSWORD])
            except DknAuthError:
                errors["base"] = "invalid_auth"
            except (DknApiError, DknConnectionError):
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=email,
                    data={CONF_EMAIL: email, CONF_PASSWORD: user_input[CONF_PASSWORD]},
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
        )
