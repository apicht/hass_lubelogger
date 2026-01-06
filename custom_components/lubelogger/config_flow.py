"""Config flow for LubeLogger integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .api import (
    LubeLoggerApiClient,
    LubeLoggerAuthError,
    LubeLoggerConnectionError,
)
from .const import (
    CONF_DISTANCE_UNIT,
    CONF_URL,
    DISTANCE_UNIT_KILOMETERS,
    DISTANCE_UNIT_MILES,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class LubeLoggerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for LubeLogger."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Create the options flow."""
        return LubeLoggerOptionsFlowHandler()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step.

        This step collects the LubeLogger URL and credentials, validates them,
        and creates a config entry if successful.
        """
        errors: dict[str, str] = {}

        if user_input is not None:
            # Normalize URL
            url = user_input[CONF_URL].rstrip("/")
            if not url.startswith(("http://", "https://")):
                url = f"https://{url}"

            try:
                # Validate credentials by testing connection
                session = async_get_clientsession(self.hass)
                client = LubeLoggerApiClient(
                    session,
                    url,
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                )

                if not await client.test_connection():
                    errors["base"] = "cannot_connect"
                else:
                    # Check if already configured with this URL
                    await self.async_set_unique_id(url)
                    self._abort_if_unique_id_configured()

                    # Create the entry
                    return self.async_create_entry(
                        title=f"LubeLogger ({url})",
                        data={
                            CONF_URL: url,
                            CONF_USERNAME: user_input[CONF_USERNAME],
                            CONF_PASSWORD: user_input[CONF_PASSWORD],
                        },
                    )

            except LubeLoggerAuthError:
                errors["base"] = "invalid_auth"
            except LubeLoggerConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception during config flow")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication.

        Called when authentication fails and credentials need to be updated.
        """
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauthentication confirmation.

        Prompts user for new credentials and validates them.
        """
        errors: dict[str, str] = {}

        if user_input is not None:
            reauth_entry = self._get_reauth_entry()
            url = reauth_entry.data[CONF_URL]

            try:
                session = async_get_clientsession(self.hass)
                client = LubeLoggerApiClient(
                    session,
                    url,
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                )

                if not await client.test_connection():
                    errors["base"] = "cannot_connect"
                else:
                    # Update the entry with new credentials
                    return self.async_update_reload_and_abort(
                        reauth_entry,
                        data={
                            CONF_URL: url,
                            CONF_USERNAME: user_input[CONF_USERNAME],
                            CONF_PASSWORD: user_input[CONF_PASSWORD],
                        },
                    )

            except LubeLoggerAuthError:
                errors["base"] = "invalid_auth"
            except LubeLoggerConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception during reauth")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )


class LubeLoggerOptionsFlowHandler(OptionsFlow):
    """Handle LubeLogger options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options.

        Allows users to configure the distance unit used in their LubeLogger instance.
        """
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        # Get current value, defaulting to miles for backwards compatibility
        current_unit = self.config_entry.options.get(
            CONF_DISTANCE_UNIT, DISTANCE_UNIT_MILES
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_DISTANCE_UNIT,
                        default=current_unit,
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                {"value": DISTANCE_UNIT_MILES, "label": "Miles"},
                                {"value": DISTANCE_UNIT_KILOMETERS, "label": "Kilometers"},
                            ],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
        )
