"""Public pure-contract behavior against isolated domain fixtures, no business originals."""

import hashlib
import importlib.util
from pathlib import Path
import shutil
import sys
import pytest
import yaml

DOMAIN = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "wifi_contract_test",
    DOMAIN / "governance/contracts/__init__.py",
    submodule_search_locations=[str(DOMAIN / "governance/contracts")],
)
contract = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = contract
spec.loader.exec_module(contract)
from wifi_contract_test import knowledge, records, source_resources, validation as v  # noqa: E402


@pytest.fixture
def rules(tmp_path):
    shutil.copytree(DOMAIN / "governance", tmp_path / "governance")
    (tmp_path / "knowledge").mkdir()
    digest = hashlib.sha256((tmp_path / "governance/framework.lock.yaml").read_bytes()).hexdigest()
    return v.load_rules(tmp_path, digest)


def card_data(**overrides):
    meta = dict(
        schema_version="2.0",
        id="card-a",
        profile="entity",
        title="对象",
        summary="职责摘要",
        lifecycle="draft",
        review_mode="manual_document",
        owner="author",
        aliases=[],
        scope={"applicability": "unknown", "contexts": []},
        sources=[
            {
                "evidence_ref": "e1",
                "source_id": "s1",
                "snapshot_id": "raw:one",
                "locator": {"kind": "lines", "start": 1, "end": 1},
            }
        ],
        claims=[
            dict(
                id="c1",
                text_ref="#c1",
                evidence_kind="design",
                source_refs=["e1"],
                context_ids=[],
                usage="guidance",
                verification_requirements=[],
            )
        ],
        relations=[],
    )
    meta.update(overrides)
    body = '# 对象\n<a id="c1"></a>\n职责说明。\n\n' + "\n".join(
        "## " + x + "\n说明\n" for x in ("职责", "边界", "接口", "依赖", "证据")
    )
    return ("---\n" + yaml.safe_dump(meta, allow_unicode=True, sort_keys=False) + "---\n" + body).encode("utf-8")


def test_exact_bytes_and_claim_locator(rules):
    data = card_data().replace(b"\n", b"\r\n")
    card = knowledge.parse_card(data, "knowledge/concepts/entities/a.md", rules)
    claim = card["claims"][0]
    assert card["raw"] == data
    assert card["body"][claim["span"]["start"] : claim["span"]["end"]] == claim["text"]
    assert "职责说明" in claim["text"]


@pytest.mark.parametrize(
    "path", ["../escape", "/tmp/a", "C:/a", "a\\b", "a//b", "a/./b", "a/.. /b", "NUL.txt", "a/x:secret", "a/trailing."]
)
def test_portable_path_rejection(rules, path):
    with pytest.raises(v.ContractError):
        v.safe_path(rules["knowledge_root"], path)


def test_path_case_alias(rules):
    (rules["knowledge_root"] / "Case.txt").write_bytes(b"a")
    with pytest.raises(v.ContractError, match="PATH_CASE_ALIAS"):
        v.safe_path(rules["knowledge_root"], "case.txt")


def test_rules_pin_blocks_program_replacement(rules):
    (rules["knowledge_root"] / "governance/contracts/records.py").write_text("raise RuntimeError()", encoding="utf-8")
    with pytest.raises(v.ContractError, match="RULE_FILE_DIGEST_MISMATCH"):
        v.load_rules(rules["knowledge_root"], rules["rules_digest"])


def test_duplicate_yaml_and_nonfinite_json_rejected(tmp_path):
    with pytest.raises(v.ContractError):
        v.load_yaml("a: 1\na: 2\n")
    (tmp_path / "a.json").write_text('{"a":NaN}', encoding="utf-8")
    with pytest.raises(v.ContractError):
        v.read_json(tmp_path / "a.json")


def test_fenced_heading_cannot_satisfy_section(rules):
    data = card_data().replace("## 依赖\n说明".encode(), "```\n## 依赖\n说明\n```".encode())
    with pytest.raises(v.ContractError, match="MISSING_SECTIONS"):
        knowledge.parse_card(data, "a.md", rules)


def test_unselected_snapshot_cannot_authorize_claim(rules):
    card = knowledge.parse_card(card_data(), "a.md", rules)
    rules["source_lock"] = {
        "schema_version": "2.0",
        "resources": [{"source_id": "s1", "kind": "raw"}],
        "snapshots": [{"snapshot_id": "raw:other", "source_id": "s1"}],
    }
    with pytest.raises(v.ContractError, match="SOURCE_SNAPSHOT_MISMATCH"):
        knowledge.validate_card(card, None, rules)


def test_duplicate_logical_source_rejected(rules):
    path = rules["knowledge_root"] / "governance/sources.lock.yaml"
    path.write_text(
        yaml.safe_dump(
            {"schema_version": "2.0", "resources": [{"source_id": "s1", "kind": "raw"}] * 2, "snapshots": []}
        ),
        encoding="utf-8",
    )
    with pytest.raises(v.ContractError, match="DUPLICATE_SOURCE"):
        source_resources.read_source_lock(rules["knowledge_root"])


def test_record_digest_not_human_authorization():
    record = records.seal({"schema_version": "2.0", "record_kind": "manual_review", "approved": True})
    assert records.verify(record) == record
    record["approved"] = False
    with pytest.raises(v.ContractError):
        records.verify(record)


def test_complete_relation_graph_and_cycles(rules):
    a = knowledge.parse_card(card_data(), "a.md", rules)
    b = knowledge.parse_card(card_data(id="card-b"), "b.md", rules)
    a["metadata"]["relations"] = [{"type": "requires", "target_card_id": "card-b", "context_ids": []}]
    with pytest.raises(v.ContractError, match="DANGLING_RELATION"):
        knowledge.validate_relations({"card-a": a})
    knowledge.validate_relations({"card-a": a, "card-b": b})
    b["metadata"]["relations"] = [{"type": "requires", "target_card_id": "card-a", "context_ids": []}]
    with pytest.raises(v.ContractError, match="RELATION_CYCLE"):
        knowledge.validate_relations({"card-a": a, "card-b": b})


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


@pytest.mark.parametrize("kind", ["manual_review", "final_view", "local_check", "apply_result", "index_manifest"])
def test_record_kind_requires_its_actual_payload(rules, kind):
    with pytest.raises(v.ContractError, match="SCHEMA_INVALID"):
        v.validate_shape(kind, {"schema_version": "2.0", "record_kind": kind}, rules)


def test_six_targets_and_three_pairs_have_consistent_identities(rules):
    def legacy_configuration():
        normalized = v.normalize_workspace(v.load_yaml(DOMAIN.parent / "config.yml"), DOMAIN.parent)
        # This test deliberately exercises the old public registration format.
        # The shipped module mapping is validated in test_workspace_mapping.py.
        fields = ("schema_version", "workspace_id", "knowledge_roots", "repos", "architecture",
                  "wiki_entities", "symbol_aliases", "targets", "pairs", "query")
        return {field: normalized[field] for field in fields}

    config = legacy_configuration()
    v.validate_shape("workspace", config, rules)
    config["targets"] = [config["targets"][0]] * 6
    with pytest.raises(v.ContractError, match="TARGET_ID_SET_INVALID"):
        v.validate_shape("workspace", config, rules)
    config = legacy_configuration()
    config["targets"][0]["chip"] = "chip08"
    with pytest.raises(v.ContractError, match="TARGET_IDENTITY_MISMATCH"):
        v.validate_shape("workspace", config, rules)
    config = legacy_configuration()
    config["pairs"] = [config["pairs"][0]] * 3
    with pytest.raises(v.ContractError, match="PAIR_ID_SET_INVALID"):
        v.validate_shape("workspace", config, rules)
    config = legacy_configuration()
    config["pairs"][0]["device_target"] = "chip08-device"
    with pytest.raises(v.ContractError, match="PAIR_TARGET_MISMATCH"):
        v.validate_shape("workspace", config, rules)


def test_card_replacement_field_cannot_hide_dangling_or_cyclic_edges(rules):
    a = knowledge.parse_card(card_data(replacement=["card-b"]), "a.md", rules)
    with pytest.raises(v.ContractError, match="DANGLING_RELATION"):
        knowledge.validate_relations({"card-a": a})
    b = knowledge.parse_card(card_data(id="card-b", replacement=["card-a"]), "b.md", rules)
    with pytest.raises(v.ContractError, match="RELATION_CYCLE"):
        knowledge.validate_relations({"card-a": a, "card-b": b})


def test_unpinned_profiles_are_not_accepted_as_a_rule_baseline(rules):
    path = rules["knowledge_root"] / "governance/framework.lock.yaml"
    lock = v.load_yaml(path)
    lock["files"] = {
        key: value for key, value in lock["files"].items() if value["path"] != "governance/schemas/profiles.yaml"
    }
    path.write_text(yaml.safe_dump(lock), encoding="utf-8")
    with pytest.raises(v.ContractError, match="UNPINNED_RULE_DECLARATION"):
        v.load_rules(rules["knowledge_root"], hashlib.sha256(path.read_bytes()).hexdigest())
