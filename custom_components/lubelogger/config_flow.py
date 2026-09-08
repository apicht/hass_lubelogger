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

from .api import (
    LubeLoggerApiClient,
    LubeLoggerAuthError,
    LubeLoggerConnectionError,
)
from .const import (
    CONF_DISTANCE_UNIT,
    CONF_DISTANCE_UNIT_CONFIRMED,
    CONF_URL,
    DOMAIN,
)
from .util import (
    default_distance_unit,
    distance_unit_selector,
    resolve_distance_unit,
)

_LOGGER = logging.getLogger(__name__)


def _user_step_schema(default_unit: str) -> vol.Schema:
    """Return the initial setup schema with the distance unit pre-selected."""
    return vol.Schema(
        {
            vol.Required(CONF_URL): str,
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
            vol.Required(
                CONF_DISTANCE_UNIT, default=default_unit
            ): distance_unit_selector(),
        }
    )


class LubeLoggerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for LubeLogger."""

    VERSION = 2

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

                    # Create the entry. The distance unit lives in options so
                    # the options flow has a single place to read and write it.
                    return self.async_create_entry(
                        title=f"LubeLogger ({url})",
                        data={
                            CONF_URL: url,
                            CONF_USERNAME: user_input[CONF_USERNAME],
                            CONF_PASSWORD: user_input[CONF_PASSWORD],
                        },
                        options={
                            CONF_DISTANCE_UNIT: user_input[CONF_DISTANCE_UNIT],
                            CONF_DISTANCE_UNIT_CONFIRMED: True,
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
            data_schema=self.add_suggested_values_to_schema(
                _user_step_schema(default_distance_unit(self.hass)),
                # Re-show what they typed, but never the password.
                {k: v for k, v in user_input.items() if k != CONF_PASSWORD}
                if user_input
                else None,
            ),
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
            # Saving the form is an explicit choice, so the unit is no longer a
            # guess and the repairs issue can be retired.
            return self.async_create_entry(
                data={**user_input, CONF_DISTANCE_UNIT_CONFIRMED: True}
            )

        # Entries created before this setting existed have nothing stored, so
        # fall back to Home Assistant's unit system rather than to miles.
        current_unit = resolve_distance_unit(self.hass, self.config_entry.options)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_DISTANCE_UNIT,
                        default=current_unit,
                    ): distance_unit_selector(),
                }
            ),
        )
