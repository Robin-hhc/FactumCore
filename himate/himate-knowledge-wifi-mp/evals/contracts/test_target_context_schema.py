"""Legacy context headers accept configured chip names without losing validation."""

import importlib.util
import json
from pathlib import Path

import pytest
import yaml


_spec = importlib.util.spec_from_file_location(
    "target_context_support", Path(__file__).resolve().parents[1] / "support/contracts.py",
)
_support = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_support)
cards = _support.module("cards_v3")
validation = _support.module("validation")


def context_card(chip):
    metadata = {
        "id": "configured-target",
        "doc_ref": [{"doc_id": "doc-design", "line_start": 1, "line_end": 1}],
        "code_ref": [],
        "scope": {"applicability": "constrained", "contexts": [{
            "context_id": "device-context", "target_id": f"{chip}-device" if chip else None,
            "chip": chip, "side": "device", "build_profile": None,
            "features_all": [], "features_none": [], "protocol_versions": [],
            "revision_policy": "not_applicable",
        }]},
    }
    return ("---\n" + yaml.safe_dump(metadata) + "---\n# Configured target\n\nA source-backed condition.\n").encode()


def rules():
    path = Path(__file__).resolve().parents[2] / "governance/schemas/frontmatter.schema.json"
    return {"schemas": {"card": json.loads(path.read_bytes())}}


@pytest.mark.parametrize("chip", ["soc-new", "chip12", None])
def test_legacy_card_context_accepts_custom_and_existing_chip_labels(chip):
    parsed = cards.parse_card(context_card(chip), "knowledge/configured-target.md", rules=rules())

    assert parsed["legacy"] is True
    assert parsed["metadata"]["scope"]["contexts"][0]["chip"] == chip


@pytest.mark.parametrize("chip", ["", " ", "\t\n"])
def test_legacy_card_context_rejects_empty_or_blank_chip_labels(chip):
    with pytest.raises(validation.ContractError, match="SCHEMA_INVALID"):
        cards.parse_card(context_card(chip), "knowledge/configured-target.md", rules=rules())
