"""Publication format is explicit about this batch's external input scope."""

import copy
import json
import importlib.util
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location("dbox_publication_cases", Path(__file__).with_name("test_publication.py"))
publication_cases = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(publication_cases)
installed_publication = publication_cases.installed_publication


@pytest.fixture
def publication_case(tmp_path):
    return publication_cases.publication_case.__wrapped__(tmp_path)


def replace_manifest(ctx, value):
    value = copy.deepcopy(value)
    value.pop("digest", None)
    value = ctx.modules["records"].seal(value)
    path = ctx.root / ("logs/publications/" + ctx.operation + "/manifest.json")
    path.write_text(json.dumps(value), encoding="utf-8")
    return value


def test_new_publication_declares_empty_dbox_execution_scope(publication_case):
    publication, ctx, manifest, _ = installed_publication(publication_case)
    assert manifest["protocol_version"] == "1.2"
    assert manifest["dbox_execution_scope"] == []
    assert publication.read_manifest(ctx) == manifest


def test_new_publication_cannot_omit_execution_scope(publication_case):
    publication, ctx, manifest, _ = installed_publication(publication_case)
    value = copy.deepcopy(manifest)
    value["protocol_version"] = "1.1"
    value.pop("dbox_execution_scope", None)
    replace_manifest(ctx, value)
    with pytest.raises(ValueError, match="(scope|Scope)"):
        publication.read_manifest(ctx)


@pytest.mark.parametrize("protocol", ["1.0", "1.1"])
def test_legacy_publication_and_completion_keep_their_original_protocol(publication_case, protocol):
    publication, ctx, manifest, _ = installed_publication(publication_case, record_only=True)
    value = copy.deepcopy(manifest)
    value["protocol_version"] = protocol
    value["rules_digest"] = "0" * 64
    value.pop("content_basis", None)
    if protocol == "1.0":
        value.pop("dbox_execution_scope", None)
    legacy = replace_manifest(ctx, value)
    assert publication.read_manifest(ctx) == legacy
    completion = publication.write_completion(ctx, legacy, data={},
        retrieval={"complete": True, "scope": "record_only"}, owned_files=[])
    assert completion["protocol_version"] == protocol
    assert publication.read_completion(ctx, legacy) == completion


def test_current_publication_cannot_drop_its_frozen_content_basis(publication_case):
    publication, ctx, manifest, _ = installed_publication(publication_case)
    value = copy.deepcopy(manifest)
    value.pop("content_basis")
    replace_manifest(ctx, value)
    with pytest.raises(ValueError, match="content basis"):
        publication.read_manifest(ctx)


@pytest.mark.parametrize("scope", [None, {}, [{"path": "../outside", "sha256": "a" * 64, "bytes": 1}],
    [{"path": "docs-raw/sources/dbox/a.md", "sha256": "a" * 64, "bytes": True}]])
def test_new_publication_validates_logical_scope(publication_case, scope):
    publication, ctx, manifest, _ = installed_publication(publication_case)
    value = copy.deepcopy(manifest)
    value.update(protocol_version="1.1", dbox_execution_scope=scope)
    replace_manifest(ctx, value)
    with pytest.raises(ValueError):
        publication.read_manifest(ctx)
