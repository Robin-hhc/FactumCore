from _shared.scope import evaluate_conditions


def test_condition_groups_are_not_recombined_into_new_target_matches():
    scope = {
        "applicability": "constrained",
        "contexts": [
            {"context_id": "a", "chip": "chip12", "side": "host"},
            {"context_id": "b", "chip": "chip08", "side": "device"},
        ],
    }
    assert evaluate_conditions(scope, {"chip": "chip12", "side": "device"})["status"] == "mismatch"
    assert evaluate_conditions(scope, {"chip": "chip12", "side": "host"})["status"] == "match"


def test_missing_required_condition_and_unknown_applicability_stay_unknown():
    scope = {
        "applicability": "constrained",
        "contexts": [
            {"context_id": "a", "chip": "chip12", "side": "host", "build_profile": "release"},
        ],
    }
    assert evaluate_conditions(scope, {"chip": "chip12", "side": "host"})["status"] == "unknown"
    assert (
        evaluate_conditions({"applicability": "unknown", "contexts": []}, {})["status"] == "unknown"
    )


def test_feature_exclusion_and_protocol_conditions_remain_in_same_group():
    scope = {
        "applicability": "constrained",
        "contexts": [
            {
                "context_id": "a",
                "chip": "chip08",
                "side": "host",
                "features_all": ["WIFI"],
                "features_none": ["LEGACY"],
                "protocol_versions": ["v2"],
            }
        ],
    }
    context = {"chip": "chip08", "side": "host", "features": ["WIFI"], "protocol_versions": ["v2"]}
    assert evaluate_conditions(scope, context)["status"] == "match"
    context["features"].append("LEGACY")
    assert evaluate_conditions(scope, context)["status"] == "mismatch"


def test_revision_policy_without_snapshot_proof_stays_unknown():
    scope = {
        "applicability": "constrained",
        "contexts": [
            {
                "context_id": "a",
                "chip": "chip12",
                "side": "host",
                "revision_policy": "pinned",
            }
        ],
    }
    for revision in ("revision-a", "revision-b", None):
        result = evaluate_conditions(
            scope, {"chip": "chip12", "side": "host", "revision": revision}
        )
        assert result["status"] == "unknown"
