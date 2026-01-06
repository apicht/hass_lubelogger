"""API client for LubeLogger."""

from __future__ import annotations

import base64
import logging
from typing import Any

from aiohttp import ClientError, ClientResponseError, ClientSession

from .const import (
    API_ADD_GAS,
    API_ADD_ODOMETER,
    API_ADD_REMINDER,
    API_VEHICLE_INFO,
    API_VEHICLES,
)

_LOGGER = logging.getLogger(__name__)


class LubeLoggerApiError(Exception):
    """Base exception for LubeLogger API errors."""


class LubeLoggerAuthError(LubeLoggerApiError):
    """Authentication error."""


class LubeLoggerConnectionError(LubeLoggerApiError):
    """Connection error."""


class LubeLoggerApiClient:
    """API client for LubeLogger."""

    def __init__(
        self,
        session: ClientSession,
        base_url: str,
        username: str,
        password: str,
    ) -> None:
        """Initialize the API client.

        Args:
            session: aiohttp client session for making requests.
            base_url: Base URL of the LubeLogger instance.
            username: Username for Basic Auth.
            password: Password for Basic Auth.
        """
        self._session = session
        self._base_url = base_url.rstrip("/")
        self._auth_header = self._create_auth_header(username, password)

    def _create_auth_header(self, username: str, password: str) -> str:
        """Create Basic Auth header value.

        Args:
            username: Username for authentication.
            password: Password for authentication.

        Returns:
            Base64-encoded Basic Auth header value.
        """
        credentials = f"{username}:{password}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded}"

    def _get_headers(self) -> dict[str, str]:
        """Return headers for API requests.

        Returns:
            Dictionary of HTTP headers including auth and culture-invariant mode.
        """
        return {
            "Authorization": self._auth_header,
            "culture-invariant": "",  # Header presence enables invariant mode
            "Content-Type": "application/json",
        }

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
    ) -> Any:
        """Make an API request.

        Args:
            method: HTTP method (GET, POST, etc.).
            endpoint: API endpoint path.
            params: Optional query parameters.
            json_data: Optional JSON body data.

        Returns:
            Parsed JSON response.

        Raises:
            LubeLoggerAuthError: If authentication fails.
            LubeLoggerConnectionError: If connection fails.
            LubeLoggerApiError: For other API errors.
        """
        url = f"{self._base_url}{endpoint}"

        try:
            async with self._session.request(
                method,
                url,
                headers=self._get_headers(),
                params=params,
                json=json_data,
                timeout=30,
            ) as response:
                if response.status in (401, 403):
                    raise LubeLoggerAuthError("Authentication failed")
                response.raise_for_status()
                return await response.json()
        except LubeLoggerAuthError:
            raise
        except ClientResponseError as err:
            if err.status in (401, 403):
                raise LubeLoggerAuthError("Authentication failed") from err
            raise LubeLoggerApiError(f"API error: {err}") from err
        except ClientError as err:
            raise LubeLoggerConnectionError(f"Connection error: {err}") from err

    async def test_connection(self) -> bool:
        """Test the API connection.

        Returns:
            True if connection is successful, False otherwise.
        """
        try:
            await self.get_vehicles()
            return True
        except LubeLoggerApiError:
            return False

    async def get_vehicles(self) -> list[dict[str, Any]]:
        """Get list of all vehicles.

        Returns:
            List of vehicle dictionaries.
        """
        return await self._request("GET", API_VEHICLES)

    async def get_vehicle_info(self, vehicle_id: int) -> dict[str, Any]:
        """Get detailed info for a specific vehicle.

        Args:
            vehicle_id: The ID of the vehicle.

        Returns:
            Vehicle info dictionary including costs, odometer, and reminders.
        """
        return await self._request(
            "GET",
            API_VEHICLE_INFO,
            params={"VehicleId": vehicle_id},
        )

    async def add_odometer_record(
        self,
        vehicle_id: int,
        date: str,
        odometer: float,
        notes: str = "",
        tags: str = "",
    ) -> dict[str, Any]:
        """Add an odometer record.

        Args:
            vehicle_id: The ID of the vehicle.
            date: Date of the reading (YYYY-MM-DD format).
            odometer: Odometer reading value.
            notes: Optional notes for the record.
            tags: Optional comma-separated tags.

        Returns:
            API response confirming the record was added.
        """
        return await self._request(
            "POST",
            API_ADD_ODOMETER,
            json_data={
                "vehicleId": vehicle_id,
                "date": date,
                "odometer": odometer,
                "notes": notes,
                "tags": tags,
            },
        )

    async def add_gas_record(
        self,
        vehicle_id: int,
        date: str,
        odometer: float,
        fuel_consumed: float,
        cost: float,
        is_fill_to_full: bool = True,
        missed_fuel_up: bool = False,
        notes: str = "",
        tags: str = "",
    ) -> dict[str, Any]:
        """Add a gas/fuel record.

        Args:
            vehicle_id: The ID of the vehicle.
            date: Date of the fuel purchase (YYYY-MM-DD format).
            odometer: Odometer reading at fill-up.
            fuel_consumed: Amount of fuel added (gallons, liters, kWh, etc.).
            cost: Total cost of the fuel.
            is_fill_to_full: Whether this was a complete fill-up.
            missed_fuel_up: Whether a previous fill-up was missed/not recorded.
            notes: Optional notes for the record.
            tags: Optional comma-separated tags.

        Returns:
            API response confirming the record was added.
        """
        return await self._request(
            "POST",
            API_ADD_GAS,
            json_data={
                "vehicleId": vehicle_id,
                "date": date,
                "odometer": odometer,
                "fuelConsumed": fuel_consumed,
                "cost": cost,
                "isFillToFull": is_fill_to_full,
                "missedFuelUp": missed_fuel_up,
                "notes": notes,
                "tags": tags,
            },
        )

    async def add_reminder(
        self,
        vehicle_id: int,
        description: str,
        due_date: str | None = None,
        due_odometer: float | None = None,
        metric: str = "Both",
        notes: str = "",
        tags: str = "",
    ) -> dict[str, Any]:
        """Add a maintenance reminder.

        Args:
            vehicle_id: The ID of the vehicle.
            description: Description of the reminder (e.g., "Oil Change").
            due_date: Optional due date (YYYY-MM-DD format).
            due_odometer: Optional odometer reading when reminder is due.
            metric: How to track the reminder ("Date", "Odometer", or "Both").
            notes: Optional notes for the reminder.
            tags: Optional comma-separated tags.

        Returns:
            API response confirming the reminder was added.
        """
        data: dict[str, Any] = {
            "vehicleId": vehicle_id,
            "description": description,
            "metric": metric,
            "notes": notes,
            "tags": tags,
        }
        if due_date:
            data["dueDate"] = due_date
        if due_odometer is not None:
            data["dueOdometer"] = due_odometer
        return await self._request("POST", API_ADD_REMINDER, json_data=data)
