"""Guards against the translation drift that hid the distance unit setting."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from homeassistant.core import HomeAssistant
from homeassistant.helpers.translation import async_get_translations

from custom_components.lubelogger.const import (
    CONF_DISTANCE_UNIT,
    DOMAIN,
    ISSUE_DISTANCE_UNIT_UNCONFIRMED,
)

COMPONENT_DIR = Path(__file__).parent.parent / "custom_components" / "lubelogger"
STRINGS = COMPONENT_DIR / "strings.json"
EN = COMPONENT_DIR / "translations" / "en.json"
SERVICES = COMPONENT_DIR / "services.yaml"


@pytest.fixture(name="strings")
def strings_fixture() -> dict:
    """Return the parsed strings.json."""
    return json.loads(STRINGS.read_text())


@pytest.fixture(name="service_fields")
def service_fields_fixture() -> dict[str, set[str]]:
    """Return the field names services.yaml declares, per service."""
    services = yaml.safe_load(SERVICES.read_text())
    return {name: set(service["fields"]) for name, service in services.items()}


def test_en_translations_match_strings(strings: dict) -> None:
    """translations/en.json is what HA actually loads for a custom integration.

    strings.json alone is not enough: it gained the options and selector
    sections while en.json kept a stale copy, so the Configure dialog rendered
    without a title or description.
    """
    assert json.loads(EN.read_text()) == strings


def test_distance_unit_is_labelled_everywhere(strings: dict) -> None:
    """Every place the unit selector appears has a label and a description."""
    for step in (strings["config"]["step"]["user"], strings["options"]["step"]["init"]):
        assert CONF_DISTANCE_UNIT in step["data"]
        assert CONF_DISTANCE_UNIT in step["data_description"]

    selector_options = strings["selector"][CONF_DISTANCE_UNIT]["options"]
    assert set(selector_options) == {"miles", "kilometers"}

    repair = strings["issues"][ISSUE_DISTANCE_UNIT_UNCONFIRMED]["fix_flow"]["step"][
        "confirm"
    ]
    assert CONF_DISTANCE_UNIT in repair["data"]
    assert CONF_DISTANCE_UNIT in repair["data_description"]


def test_repair_issue_is_translated(strings: dict) -> None:
    """The repairs issue needs a title and a fix flow, or it renders bare."""
    issue = strings["issues"][ISSUE_DISTANCE_UNIT_UNCONFIRMED]
    assert issue["title"]
    assert issue["fix_flow"]["step"]["confirm"]["description"]
    assert issue["fix_flow"]["abort"]["entry_not_found"]


async def _resolved(hass: HomeAssistant, category: str) -> dict[str, str]:
    """Return the translations Home Assistant actually resolves at runtime."""
    return await async_get_translations(hass, "en", category, {DOMAIN})


async def test_repair_translations_resolve_at_runtime(hass: HomeAssistant) -> None:
    """Assert the keys HA looks up, not just the shape of the JSON.

    A key nested one level wrong still satisfies the structural tests above and
    passes hassfest, then renders as a blank card. Only resolution catches it.
    """
    issues = await _resolved(hass, "issues")
    prefix = f"component.{DOMAIN}.issues.{ISSUE_DISTANCE_UNIT_UNCONFIRMED}"

    for key in (
        f"{prefix}.title",
        f"{prefix}.fix_flow.step.confirm.title",
        f"{prefix}.fix_flow.step.confirm.description",
        f"{prefix}.fix_flow.step.confirm.data.{CONF_DISTANCE_UNIT}",
        f"{prefix}.fix_flow.step.confirm.data_description.{CONF_DISTANCE_UNIT}",
        f"{prefix}.fix_flow.abort.entry_not_found",
    ):
        assert issues.get(key), f"unresolved: {key}"

    # The title is rendered with a placeholder the issue must supply.
    assert "{title}" in issues[f"{prefix}.title"]


async def test_selector_labels_resolve_at_runtime(hass: HomeAssistant) -> None:
    """The dropdown gets its labels from translations, not hardcoded strings."""
    selector = await _resolved(hass, "selector")

    assert (
        selector[f"component.{DOMAIN}.selector.{CONF_DISTANCE_UNIT}.options.miles"]
        == "Miles"
    )
    assert (
        selector[f"component.{DOMAIN}.selector.{CONF_DISTANCE_UNIT}.options.kilometers"]
        == "Kilometers"
    )


@pytest.mark.parametrize(
    ("category", "step_path"),
    [("config", "config.step.user"), ("options", "options.step.init")],
)
async def test_unit_field_resolves_in_both_flows(
    hass: HomeAssistant, category: str, step_path: str
) -> None:
    """Both places the field appears have a resolvable label and description."""
    translations = await _resolved(hass, category)
    base = f"component.{DOMAIN}.{step_path}"

    assert translations.get(f"{base}.data.{CONF_DISTANCE_UNIT}")
    assert translations.get(f"{base}.data_description.{CONF_DISTANCE_UNIT}")


def test_service_fields_are_documented(
    strings: dict, service_fields: dict[str, set[str]]
) -> None:
    """services.yaml and strings.json must name the same fields.

    The services took a `device_id` device picker from the day the device
    selector landed, but the translations still documented the `vehicle_id`
    field it replaced: three dead keys, and no label for the field that is
    actually there.
    """
    assert set(strings["services"]) == set(service_fields)

    for service, fields in service_fields.items():
        documented = set(strings["services"][service]["fields"])
        assert documented == fields, (
            f"{service}: undocumented {sorted(fields - documented)}, "
            f"stale {sorted(documented - fields)}"
        )


async def test_service_field_labels_resolve_at_runtime(
    hass: HomeAssistant, service_fields: dict[str, set[str]]
) -> None:
    """Every field HA renders needs a resolvable name and description."""
    services = await _resolved(hass, "services")

    for service, fields in service_fields.items():
        for field in fields:
            prefix = f"component.{DOMAIN}.services.{service}.fields.{field}"
            assert services.get(f"{prefix}.name"), f"unresolved: {prefix}.name"
            assert services.get(
                f"{prefix}.description"
            ), f"unresolved: {prefix}.description"
