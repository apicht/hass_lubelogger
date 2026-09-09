"""Guards the metadata that makes a tagged release installable by HACS."""

import json
import pathlib
import re

import yaml

REPO_ROOT = pathlib.Path(__file__).parent.parent


def load_hacs_json() -> dict:
    return json.loads((REPO_ROOT / "hacs.json").read_text())


def load_manifest() -> dict:
    manifest = REPO_ROOT / "custom_components" / "lubelogger" / "manifest.json"
    return json.loads(manifest.read_text())


def test_hacs_json_declares_a_zip_release() -> None:
    """HACS only looks for a release asset when zip_release is set."""
    hacs = load_hacs_json()

    assert hacs["zip_release"] is True
    assert hacs["filename"] == "lubelogger.zip"


def test_hacs_json_keeps_its_existing_keys() -> None:
    """The zip keys are additive; name and homeassistant must survive."""
    hacs = load_hacs_json()

    assert hacs["name"] == "LubeLogger"
    assert hacs["homeassistant"] == "2025.12.0"


def test_manifest_version_is_a_release_version() -> None:
    """Tags are derived from this value, so it must be plain semver."""
    version = load_manifest()["version"]

    assert re.fullmatch(r"\d+\.\d+\.\d+", version), version


def load_release_workflow() -> dict:
    workflow = REPO_ROOT / ".github" / "workflows" / "release.yml"
    return yaml.safe_load(workflow.read_text())


def test_release_workflow_triggers_on_version_tags() -> None:
    """In YAML 1.1 the bare key `on` parses as True, hence the fallback."""
    workflow = load_release_workflow()
    triggers = workflow.get("on", workflow.get(True))

    assert triggers["push"]["tags"] == ["v*"]


def test_release_workflow_builds_the_filename_hacs_expects() -> None:
    """Renaming one side without the other breaks every HACS install."""
    workflow = load_release_workflow()
    filename = load_hacs_json()["filename"]

    scripts = "\n".join(
        step["run"]
        for job in workflow["jobs"].values()
        for step in job["steps"]
        if "run" in step
    )

    assert filename in scripts
