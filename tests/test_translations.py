"""Guards against the translation drift that hid the distance unit setting."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from custom_components.lubelogger.const import CONF_DISTANCE_UNIT

COMPONENT_DIR = Path(__file__).parent.parent / "custom_components" / "lubelogger"
STRINGS = COMPONENT_DIR / "strings.json"
EN = COMPONENT_DIR / "translations" / "en.json"


@pytest.fixture(name="strings")
def strings_fixture() -> dict:
    """Return the parsed strings.json."""
    return json.loads(STRINGS.read_text())


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
