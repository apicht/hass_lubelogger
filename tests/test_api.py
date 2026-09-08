"""Tests for the LubeLogger HTTP client.

These are the only tests that drive the real ``LubeLoggerApiClient``; every
other test module replaces it with the ``mock_api`` fixture, which is why the
HTTP layer went uncovered until now. Requests are answered by Home Assistant's
own ``AiohttpClientMocker`` (shipped with pytest-homeassistant-custom-component)
so no socket is ever opened.
"""

from __future__ import annotations

import asyncio
import base64
from collections.abc import AsyncGenerator, Awaitable, Callable
from typing import Any

import pytest
from aiohttp import ClientConnectionError, ClientResponseError
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.lubelogger.api import (
    LubeLoggerApiClient,
    LubeLoggerApiError,
    LubeLoggerAuthError,
    LubeLoggerConnectionError,
)

from .conftest import ODOMETER_RAW

BASE_URL = "https://lubelogger.example"
USERNAME = "user"
PASSWORD = "pass"

VEHICLE_ID = 1
DATE = "2026-02-14"

# Every public call on the client, so header and URL contracts can be asserted
# across the whole surface rather than on whichever endpoint a test picked.
ENDPOINTS: list[tuple[str, str, str, Callable[[LubeLoggerApiClient], Awaitable[Any]]]] = [
    ("get_vehicles", "get", "/api/vehicles", lambda c: c.get_vehicles()),
    (
        "get_vehicle_info",
        "get",
        "/api/vehicle/info",
        lambda c: c.get_vehicle_info(VEHICLE_ID),
    ),
    (
        "get_gas_records",
        "get",
        "/api/vehicle/gasrecords",
        lambda c: c.get_gas_records(VEHICLE_ID),
    ),
    (
        "add_odometer_record",
        "post",
        "/api/vehicle/odometerrecords/add",
        lambda c: c.add_odometer_record(VEHICLE_ID, DATE, 100),
    ),
    (
        "add_gas_record",
        "post",
        "/api/vehicle/gasrecords/add",
        lambda c: c.add_gas_record(VEHICLE_ID, DATE, 100, 10.5, 42.75),
    ),
    (
        "add_reminder",
        "post",
        "/api/vehicle/reminders/add",
        lambda c: c.add_reminder(VEHICLE_ID, "Oil change"),
    ),
]

ENDPOINT_IDS = [endpoint[0] for endpoint in ENDPOINTS]


@pytest.fixture
def mocker() -> AiohttpClientMocker:
    """Return a request mocker that records every call made through it."""
    return AiohttpClientMocker()


@pytest.fixture
async def client(mocker: AiohttpClientMocker) -> AsyncGenerator[LubeLoggerApiClient]:
    """Return a real API client whose session is answered by the mocker."""
    session = mocker.create_session(asyncio.get_running_loop())
    try:
        yield LubeLoggerApiClient(session, BASE_URL, USERNAME, PASSWORD)
    finally:
        await session.close()


def _only_call(mocker: AiohttpClientMocker) -> tuple[Any, Any, Any, Any]:
    """Return the single (method, url, body, headers) request that was made."""
    assert mocker.call_count == 1, f"expected 1 request, got {mocker.call_count}"
    return mocker.mock_calls[0]


@pytest.mark.parametrize(
    ("_name", "method", "path", "call"), ENDPOINTS, ids=ENDPOINT_IDS
)
async def test_every_endpoint_sends_the_culture_invariant_header(
    mocker: AiohttpClientMocker,
    client: LubeLoggerApiClient,
    _name: str,
    method: str,
    path: str,
    call: Callable[[LubeLoggerApiClient], Awaitable[Any]],
) -> None:
    """The header's presence is what keeps LubeLogger's numbers parseable.

    Without it a non-English instance formats numbers for its own locale and
    returns e.g. ``64.526`` for a 64526 km odometer, which is the bug from #2.
    The value is deliberately empty - LubeLogger only checks for presence - so
    a regression here is invisible until someone with a German locale reports
    a mangled reading.
    """
    getattr(mocker, method)(f"{BASE_URL}{path}", json=[])

    await call(client)

    _, _, _, headers = _only_call(mocker)
    assert "culture-invariant" in headers


@pytest.mark.parametrize(
    ("_name", "method", "path", "call"), ENDPOINTS, ids=ENDPOINT_IDS
)
async def test_every_endpoint_sends_basic_auth(
    mocker: AiohttpClientMocker,
    client: LubeLoggerApiClient,
    _name: str,
    method: str,
    path: str,
    call: Callable[[LubeLoggerApiClient], Awaitable[Any]],
) -> None:
    """Every request carries credentials; LubeLogger has no session cookie."""
    getattr(mocker, method)(f"{BASE_URL}{path}", json=[])

    await call(client)

    _, _, _, headers = _only_call(mocker)
    expected = base64.b64encode(f"{USERNAME}:{PASSWORD}".encode()).decode()
    assert headers["Authorization"] == f"Basic {expected}"


async def test_auth_header_decodes_to_the_configured_credentials(
    mocker: AiohttpClientMocker,
) -> None:
    """The header round-trips, so a wrong padding or encoding would show up.

    Asserting the decoded form rather than the literal base64 string means the
    test describes the wire contract instead of restating the implementation.
    """
    session = mocker.create_session(asyncio.get_running_loop())
    try:
        client = LubeLoggerApiClient(session, BASE_URL, "aaron", "p4ssw0rd")
    finally:
        await session.close()

    encoded = client._get_headers()["Authorization"].removeprefix("Basic ")

    assert base64.b64decode(encoded).decode() == "aaron:p4ssw0rd"


async def test_colon_in_username_is_encoded_without_complaint(
    mocker: AiohttpClientMocker,
) -> None:
    """The client does not reject a colon, which is why the README forbids one.

    Basic Auth splits the decoded credential at the first colon, so a username
    containing one silently shifts the boundary: "us:er" / "pass" is sent as
    the byte-identical credential for username "us" and password "er:pass".
    The client neither validates nor escapes it, so the failure surfaces as an
    unexplained 401 from LubeLogger. This test pins that behaviour so the
    documented constraint stays true; add validation and it should fail.
    """
    session = mocker.create_session(asyncio.get_running_loop())
    try:
        ambiguous = LubeLoggerApiClient(session, BASE_URL, "us:er", "pass")
        shifted = LubeLoggerApiClient(session, BASE_URL, "us", "er:pass")
    finally:
        await session.close()

    assert ambiguous._get_headers()["Authorization"] == (
        shifted._get_headers()["Authorization"]
    )


async def test_trailing_slash_on_the_base_url_is_stripped(
    mocker: AiohttpClientMocker,
) -> None:
    """A URL pasted with a trailing slash must not produce ``//api/vehicles``.

    The config flow accepts whatever the user types, and LubeLogger 404s on the
    doubled slash.
    """
    mocker.get(f"{BASE_URL}/api/vehicles", json=[])
    session = mocker.create_session(asyncio.get_running_loop())
    try:
        client = LubeLoggerApiClient(session, f"{BASE_URL}/", USERNAME, PASSWORD)
        await client.get_vehicles()
    finally:
        await session.close()

    _, url, _, _ = _only_call(mocker)
    assert url.path == "/api/vehicles"


@pytest.mark.parametrize(
    ("_name", "method", "path", "call", "expected_param"),
    [
        (*endpoint, "VehicleId" if endpoint[0] == "get_vehicle_info" else "vehicleId")
        for endpoint in ENDPOINTS
        if endpoint[0] != "get_vehicles"
    ],
    ids=[name for name in ENDPOINT_IDS if name != "get_vehicles"],
)
async def test_vehicle_id_parameter_casing_is_per_endpoint(
    mocker: AiohttpClientMocker,
    client: LubeLoggerApiClient,
    _name: str,
    method: str,
    path: str,
    call: Callable[[LubeLoggerApiClient], Awaitable[Any]],
    expected_param: str,
) -> None:
    """``/api/vehicle/info`` wants ``VehicleId``; the rest want ``vehicleId``.

    LubeLogger's query binding is case-sensitive, so "tidying" these to one
    spelling makes the endpoint fall back to vehicle 0 and return nothing.
    """
    getattr(mocker, method)(f"{BASE_URL}{path}", json=[])

    await call(client)

    _, url, _, _ = _only_call(mocker)
    assert url.query[expected_param] == str(VEHICLE_ID)


async def test_vehicle_info_is_returned_exactly_as_sent(
    mocker: AiohttpClientMocker,
    client: LubeLoggerApiClient,
    vehicle_info: list[dict[str, Any]],
) -> None:
    """The client hands back the single-element list, it does not unwrap it.

    LubeLogger really does wrap one vehicle's stats in a list. Unwrapping is
    the coordinator's job, so if the client started returning ``[0]`` here the
    coordinator's own list handling would merge a bare float into its data.
    """
    mocker.get(f"{BASE_URL}/api/vehicle/info", json=vehicle_info)

    result = await client.get_vehicle_info(VEHICLE_ID)

    assert result == vehicle_info
    assert result[0]["lastReportedOdometer"] == ODOMETER_RAW


@pytest.mark.parametrize("status", [401, 403], ids=["unauthorized", "forbidden"])
async def test_rejected_credentials_raise_auth_error(
    mocker: AiohttpClientMocker, client: LubeLoggerApiClient, status: int
) -> None:
    """Only ``LubeLoggerAuthError`` triggers HA's reauth flow.

    The coordinator maps it to ``ConfigEntryAuthFailed``; anything else becomes
    a retried ``UpdateFailed``, so a rotated password would silently retry
    forever instead of prompting the user.
    """
    mocker.get(f"{BASE_URL}/api/vehicles", status=status)

    with pytest.raises(LubeLoggerAuthError):
        await client.get_vehicles()


@pytest.mark.parametrize("status", [401, 403], ids=["unauthorized", "forbidden"])
async def test_auth_failure_raised_as_client_response_error_is_still_auth_error(
    mocker: AiohttpClientMocker, client: LubeLoggerApiClient, status: int
) -> None:
    """A 401 can arrive as a raised ``ClientResponseError`` rather than a status.

    aiohttp raises it itself on a redirect chain or when ``raise_for_status`` is
    configured on the session, and HA's shared session may be. Both routes must
    end in the reauth-triggering error.
    """
    mocker.get(
        f"{BASE_URL}/api/vehicles",
        exc=ClientResponseError(request_info=None, history=(), status=status),
    )

    with pytest.raises(LubeLoggerAuthError):
        await client.get_vehicles()


async def test_server_error_raises_api_error(
    mocker: AiohttpClientMocker, client: LubeLoggerApiClient
) -> None:
    """A 500 is not an auth problem, so it must not trigger reauth.

    Mapping it to ``LubeLoggerAuthError`` would pop a "reconfigure" repair at
    the user every time their instance hiccuped.
    """
    mocker.get(f"{BASE_URL}/api/vehicles", status=500)

    with pytest.raises(LubeLoggerApiError) as err:
        await client.get_vehicles()

    assert not isinstance(err.value, LubeLoggerAuthError)


async def test_unreachable_host_raises_connection_error(
    mocker: AiohttpClientMocker, client: LubeLoggerApiClient
) -> None:
    """A dropped connection is retryable and must stay distinct from a 5xx.

    The coordinator words its ``UpdateFailed`` differently for the two, and the
    config flow reports ``cannot_connect`` only for this one.
    """
    mocker.get(f"{BASE_URL}/api/vehicles", exc=ClientConnectionError("no route"))

    with pytest.raises(LubeLoggerConnectionError):
        await client.get_vehicles()


@pytest.mark.parametrize(
    ("status", "expected"), [(200, True), (500, False)], ids=["reachable", "erroring"]
)
async def test_test_connection_answers_instead_of_raising(
    mocker: AiohttpClientMocker,
    client: LubeLoggerApiClient,
    status: int,
    expected: bool,
) -> None:
    """The config flow branches on the bool, so it must never see an exception."""
    mocker.get(f"{BASE_URL}/api/vehicles", status=status, json=[])

    assert await client.test_connection() is expected


@pytest.mark.parametrize(
    ("path", "field", "call"),
    [
        (
            "/api/vehicle/odometerrecords/add",
            "odometer",
            lambda c: c.add_odometer_record(VEHICLE_ID, DATE, 64526.9),
        ),
        (
            "/api/vehicle/gasrecords/add",
            "odometer",
            lambda c: c.add_gas_record(VEHICLE_ID, DATE, 64526.9, 10.5, 42.75),
        ),
        (
            "/api/vehicle/reminders/add",
            "dueOdometer",
            lambda c: c.add_reminder(VEHICLE_ID, "Oil change", due_odometer=64526.9),
        ),
    ],
    ids=["odometer_record", "gas_record", "reminder"],
)
async def test_odometer_values_are_truncated_to_integers(
    mocker: AiohttpClientMocker,
    client: LubeLoggerApiClient,
    path: str,
    field: str,
    call: Callable[[LubeLoggerApiClient], Awaitable[Any]],
) -> None:
    """LubeLogger stores odometers as integers and rejects a decimal.

    Automations feed these from a template sensor, which yields floats, so
    dropping the cast would make every service call from an automation fail.
    """
    mocker.post(f"{BASE_URL}{path}", json={})

    await call(client)

    _, _, body, _ = _only_call(mocker)
    assert body[field] == 64526


async def test_gas_record_keeps_fuel_and_cost_as_floats(
    mocker: AiohttpClientMocker, client: LubeLoggerApiClient
) -> None:
    """Only the odometer is an integer; truncating cost would lose cents."""
    mocker.post(f"{BASE_URL}/api/vehicle/gasrecords/add", json={})

    await client.add_gas_record(VEHICLE_ID, DATE, 100, 10.512, 42.75)

    _, _, body, _ = _only_call(mocker)
    assert body["fuelConsumed"] == 10.512
    assert body["cost"] == 42.75


async def test_state_of_charge_is_omitted_when_not_supplied(
    mocker: AiohttpClientMocker, client: LubeLoggerApiClient
) -> None:
    """Sending ``null`` is not the same as sending nothing.

    LubeLogger substitutes its own 20/80 defaults when the fields are absent,
    but writes a literal null over them when they are present and empty, which
    breaks the EV efficiency figures for non-EV fill-ups.
    """
    mocker.post(f"{BASE_URL}/api/vehicle/gasrecords/add", json={})

    await client.add_gas_record(VEHICLE_ID, DATE, 100, 10.5, 42.75)

    _, _, body, _ = _only_call(mocker)
    assert "startingSoc" not in body
    assert "endingSoc" not in body


async def test_state_of_charge_is_sent_as_an_integer_when_supplied(
    mocker: AiohttpClientMocker, client: LubeLoggerApiClient
) -> None:
    """A percentage from a template sensor arrives as a float and must be cast."""
    mocker.post(f"{BASE_URL}/api/vehicle/gasrecords/add", json={})

    await client.add_gas_record(
        VEHICLE_ID, DATE, 100, 10.5, 42.75, starting_soc=21.7, ending_soc=80.4
    )

    _, _, body, _ = _only_call(mocker)
    assert body["startingSoc"] == 21
    assert body["endingSoc"] == 80


async def test_reminder_omits_the_due_fields_it_was_not_given(
    mocker: AiohttpClientMocker, client: LubeLoggerApiClient
) -> None:
    """A date-only reminder must not also claim a due odometer of 0.

    LubeLogger treats a present ``dueOdometer`` as authoritative, so a stray 0
    marks the reminder overdue the moment it is created.
    """
    mocker.post(f"{BASE_URL}/api/vehicle/reminders/add", json={})

    await client.add_reminder(VEHICLE_ID, "Oil change", due_date=DATE)

    _, _, body, _ = _only_call(mocker)
    assert body["dueDate"] == DATE
    assert "dueOdometer" not in body
