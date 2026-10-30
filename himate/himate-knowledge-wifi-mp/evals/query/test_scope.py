"""Conservative purpose and applicability rules, independent of ingest stages."""

import importlib.util
from pathlib import Path


_spec = importlib.util.spec_from_file_location("scope_support", Path(__file__).parents[1] / "support/contracts.py")
_helper = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_helper)
knowledge = _helper.module("knowledge")


def test_unknown_scope_never_becomes_current():
    claim = {"usage": "current", "evidence_kind": "design", "scope": {"applicability": "unknown", "contexts": []}}
    assert not knowledge.match_scope(claim, {}, "current")
    assert knowledge.match_scope(claim, {}, "guidance")
    assert not knowledge.match_scope(claim, {}, "implementation")


def test_group_conditions_and_pair_are_not_relaxed():
    claim = {
        "usage": "current",
        "scope": {
            "applicability": "constrained",
            "contexts": [
                {
                    "chip": "chip12",
                    "side": "host",
                    "features_all": ["A"],
                    "features_none": ["B"],
                    "pairing_id": "chip12-host-device",
                }
            ],
        },
    }
    good = {"chip": "chip12", "side": "host", "features": ["A"], "pairing_id": "chip12-host-device"}
    assert knowledge.match_scope(claim, good)
    for field in ("chip", "side", "pairing_id"):
        other = dict(good)
        other[field] = "wrong"
        assert not knowledge.match_scope(claim, other)
    other = dict(good)
    other["features"] = ["A", "B"]
    assert not knowledge.match_scope(claim, other)


def test_empty_context_never_grants_current_scope():
    claim = {
        "usage": "current",
        "scope": {
            "applicability": "constrained",
            "contexts": [
                {
                    "context_id": "empty",
                    "target_id": None,
                    "chip": None,
                    "side": None,
                    "build_profile": None,
                    "features_all": [],
                    "features_none": [],
                    "protocol_versions": [],
                    "revision_policy": "revalidate",
                }
            ],
        },
    }
    assert not knowledge.match_scope(claim, {}, "current")


def test_unknown_features_cannot_prove_required_or_excluded_features():
    claim = {"usage": "current", "scope": {"applicability": "constrained", "contexts": [{"chip": "chip12", "features_none": ["A"]}]}}
    assert not knowledge.match_scope(claim, {"chip": "chip12", "features": None})
    assert knowledge.match_scope(claim, {"chip": "chip12", "features": []})


def test_guidance_only_implementation_text_never_becomes_current_implementation():
    claim = {"usage": "guidance", "evidence_kind": "implementation", "scope": {"applicability": "universal", "contexts": []}}
    assert not knowledge.match_scope(claim, {}, "implementation")
