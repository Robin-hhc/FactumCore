"""Public, language-independent evidence capture and relocation contracts."""

import base64
import importlib.util
import json
from pathlib import Path
import re

import pytest


MODULE = Path(__file__).resolve().parents[2] / "runtime/governance/contracts/code_evidence.py"
spec = importlib.util.spec_from_file_location("code_evidence_contract", MODULE)
evidence = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evidence)

CONTEXT = ("before one\nbefore two\nbefore three\n"
           "target one\ntarget two\n"
           "after one\nafter two\nafter three\n")


@pytest.mark.parametrize("text,start,end", [
    ("header\n#define LIMIT 3\nfooter\n", 2, 2),
    ("header\n#define APPLY(x) \\\n    ((x) + 1)\nfooter\n", 2, 3),
    ("header\nif enabled:\n    result = value + 1\nfooter\n", 2, 3),
    ("header\n{\"key\": \"value\"}\nfooter\n", 2, 2),
    ("header\n任意证据片段\nfooter\n", 2, 2),
])
def test_captures_arbitrary_complete_text_lines(text, start, end):
    version = evidence.capture(text, start, end)
    assert re.fullmatch(r"fc-code-lines-v1:sha256:[a-f0-9]{64}:[A-Za-z0-9_-]+", version)
    result = evidence.resolve(text, start, end, version)
    assert result["status"] == "fresh"
    assert (result["line_start"], result["line_end"]) == (start, end)
    assert result["evidence_version"] == version
    assert result["content"] == "".join(text.splitlines(keepends=True)[start - 1:end])


def test_inserting_lines_relocates_evidence_without_reconfirming_content():
    version = evidence.capture(CONTEXT, 4, 5)
    result = evidence.resolve("inserted one\ninserted two\n" + CONTEXT, 4, 5, version)
    assert result == {"status": "relocated", "line_start": 6, "line_end": 7,
                      "evidence_version": version, "content": "target one\ntarget two\n"}


def test_deleting_preceding_lines_relocates_evidence_upward():
    version = evidence.capture(CONTEXT, 4, 5)
    result = evidence.resolve(CONTEXT.removeprefix("before one\nbefore two\n"), 4, 5, version)
    assert result["status"] == "relocated"
    assert (result["line_start"], result["line_end"]) == (2, 3)
    assert result["evidence_version"] == version


def test_out_of_bounds_old_hint_does_not_prevent_relocation():
    original = "a\nb\nc\nd\nTARGET\nend\n"
    version = evidence.capture(original, 5, 5)
    result = evidence.resolve("TARGET\n", 5, 5, version)
    assert result["status"] == "relocated"
    assert (result["line_start"], result["line_end"]) == (1, 1)


def test_changes_outside_selected_range_keep_existing_version():
    version = evidence.capture(CONTEXT, 4, 5)
    current = CONTEXT.replace("before one", "changed before").replace("after three", "changed after")
    result = evidence.resolve(current, 4, 5, version)
    assert result["status"] == "fresh"
    assert result["evidence_version"] == version


@pytest.mark.parametrize("prefix,replacement,expected_range", [
    ("", "target changed\ntarget two\n", (4, 5)),
    ("", "target one\nnew target line\ntarget two\n", (4, 6)),
    ("inserted one\ninserted two\n", "target one\nnew target line\ntarget two\n", (6, 8)),
    ("", "target changed\n", (4, 4)),
])
def test_context_anchors_locate_changed_ranges_without_accepting_new_content(prefix, replacement, expected_range):
    version = evidence.capture(CONTEXT, 4, 5)
    current = prefix + CONTEXT.replace("target one\ntarget two\n", replacement)
    result = evidence.resolve(current, 4, 5, version)
    assert result["status"] == "changed"
    assert (result["line_start"], result["line_end"]) == expected_range
    assert result["content"] == replacement
    assert result["evidence_version"] != version
    # The proposed version becomes fresh only when the caller explicitly stores it.
    accepted = evidence.resolve(current, *expected_range, result["evidence_version"])
    assert accepted["status"] == "fresh"


def test_deleted_selected_range_is_unresolved():
    version = evidence.capture(CONTEXT, 4, 5)
    current = CONTEXT.replace("target one\ntarget two\n", "")
    assert evidence.resolve(current, 4, 5, version) == {"status": "unresolved"}


def test_deleted_whole_file_is_unresolved():
    version = evidence.capture("only selected content\n", 1, 1)
    assert evidence.resolve("", 1, 1, version) == {"status": "unresolved"}


def test_duplicate_exact_matches_can_be_disambiguated_by_exterior_context():
    version = evidence.capture(CONTEXT, 4, 5)
    decoy = ("wrong one\nwrong two\nwrong three\ntarget one\ntarget two\n"
             "wrong four\nwrong five\nwrong six\n")
    result = evidence.resolve("inserted\n" + decoy + CONTEXT, 4, 5, version)
    assert result["status"] == "relocated"
    assert (result["line_start"], result["line_end"]) == (13, 14)


def test_ambiguous_exact_matches_are_not_arbitrarily_selected():
    version = evidence.capture(CONTEXT, 4, 5)
    assert evidence.resolve("inserted\n" + CONTEXT + CONTEXT, 4, 5, version) == {"status": "unresolved"}


def test_ambiguous_changed_anchors_are_unresolved():
    version = evidence.capture(CONTEXT, 4, 5)
    block = CONTEXT.replace("target one\ntarget two\n", "changed\n")
    assert evidence.resolve(block + block, 4, 5, version) == {"status": "unresolved"}


def test_unique_exact_match_is_content_relocation_not_object_identity_proof():
    old = "int retry_limit(void) {\n    return 3;\n}\n"
    version = evidence.capture(old, 2, 2)
    current = ("int retry_limit(void) {\n    return 5;\n}\n"
               "int debug_default(void) {\n    return 3;\n}\n")
    result = evidence.resolve(current, 2, 2, version)
    assert result["status"] == "relocated"
    assert (result["line_start"], result["line_end"]) == (5, 5)
    assert result["evidence_version"] == version


@pytest.mark.parametrize("version", [None, "", "unknown-version", 3, {},
    "fc-code-lines-v2:sha256:" + "0" * 64 + ":e30",
    "fc-code-lines-v1:sha256:bad:e30",
    "fc-code-lines-v1:sha256:" + "0" * 64 + ":not+base64",
    "fc-code-lines-v1:sha256:" + "0" * 64 + ":e30",
])
def test_unknown_or_malformed_versions_do_not_establish_a_baseline(version):
    assert evidence.resolve(CONTEXT, 4, 5, version) == {"status": "unversioned"}


@pytest.mark.parametrize("mutation", [
    {"selectedLineCount": 0}, {"selectedLineCount": True}, {"selectedLineCount": 2**53},
    {"precedingContextLineCount": 4}, {"followingContextLineCount": -1},
    {"firstSelectedLineHash": "not-a-hash"}, {"lastSelectedLineHash": "A" * 64},
    {"extra": 1},
])
def test_corrupt_relocation_metadata_is_not_a_reviewed_version(mutation):
    prefix, digest, encoded = evidence.capture(CONTEXT, 4, 5).rsplit(":", 2)
    metadata = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
    metadata.update(mutation)
    corrupted = base64.urlsafe_b64encode(json.dumps(metadata).encode()).decode().rstrip("=")
    assert evidence.resolve(CONTEXT, 4, 5, f"{prefix}:{digest}:{corrupted}") == {"status": "unversioned"}


def test_crlf_and_lf_share_the_documented_evidence_profile():
    version = evidence.capture(CONTEXT.replace("\n", "\r\n"), 4, 5)
    assert version == evidence.capture(CONTEXT, 4, 5)
    result = evidence.resolve("inserted\r\n" + CONTEXT.replace("\n", "\r\n"), 4, 5, version)
    assert result["status"] == "relocated"
    assert result["content"] == "target one\ntarget two\n"


def test_string_and_indentation_whitespace_are_not_folded():
    original = CONTEXT.replace("target one", '    return "a  b";')
    version = evidence.capture(original, 4, 5)
    for current in (original.replace('"a  b"', '"a b"'), original.replace("    return", "  return")):
        result = evidence.resolve(current, 4, 5, version)
        assert result["status"] == "changed"
        assert result["evidence_version"] != version


def test_unicode_line_separators_and_carriage_returns_are_not_extra_lines():
    text = "one\u2028still one\rstill one\nsecond\n"
    version = evidence.capture(text, 1, 1)
    result = evidence.resolve(text, 1, 1, version)
    assert result["content"] == "one\u2028still one\rstill one\n"
    assert result["line_end"] == 1


def test_terminal_newline_does_not_create_a_phantom_line():
    assert evidence.resolve("last\n", 1, 1, evidence.capture("last\n", 1, 1))["status"] == "fresh"
    with pytest.raises(ValueError):
        evidence.capture("last\n", 2, 2)
    assert evidence.resolve("last", 1, 1, evidence.capture("last", 1, 1))["content"] == "last"


@pytest.mark.parametrize("text,start,end", [
    ("", 1, 1), ("one\n", 0, 1), ("one\n", 2, 1),
    ("one\n", True, 1), ("one\n", 1, False), ("one\n", 1.0, 1),
    (b"one\n", 1, 1),
])
def test_capture_rejects_invalid_text_or_range(text, start, end):
    with pytest.raises(ValueError):
        evidence.capture(text, start, end)


def test_optional_per_file_cache_never_reuses_another_texts_observations():
    cache = {}
    version = evidence.capture(CONTEXT, 4, 5, cache=cache)
    current = "inserted\n" + CONTEXT
    assert evidence.resolve(current, 4, 5, version, cache=cache) == evidence.resolve(current, 4, 5, version)
    modified = current.replace("target one", "modified target")
    assert evidence.resolve(modified, 4, 5, version, cache=cache) == evidence.resolve(modified, 4, 5, version)
    assert evidence.resolve(CONTEXT, 4, 5, version, cache=cache)["status"] == "fresh"


def test_persisted_relocated_hint_is_fresh_on_the_next_pass():
    version = evidence.capture(CONTEXT, 4, 5)
    current = "inserted one\ninserted two\n" + CONTEXT
    moved = evidence.resolve(current, 4, 5, version)
    again = evidence.resolve(current, moved["line_start"], moved["line_end"], moved["evidence_version"])
    assert again["status"] == "fresh"
    assert again["evidence_version"] == version


def test_whole_file_selection_has_defined_boundary_anchors():
    version = evidence.capture("old\n", 1, 1)
    changed = evidence.resolve("replacement\nextra\n", 1, 1, version)
    assert changed["status"] == "changed"
    assert (changed["line_start"], changed["line_end"]) == (1, 2)
    assert changed["content"] == "replacement\nextra\n"


def test_exterior_anchors_in_reverse_order_do_not_create_a_range():
    version = evidence.capture(CONTEXT, 4, 5)
    current = ("after one\nafter two\nafter three\n"
               "before one\nbefore two\nbefore three\n")
    assert evidence.resolve(current, 4, 5, version) == {"status": "unresolved"}


@pytest.mark.parametrize("start,end", [(0, 1), (2, 1), (True, 1), (1, "2")])
def test_resolve_rejects_malformed_line_hints(start, end):
    with pytest.raises(ValueError):
        evidence.resolve(CONTEXT, start, end, evidence.capture(CONTEXT, 4, 5))


def test_cache_must_be_an_explicit_caller_owned_dictionary():
    with pytest.raises(ValueError):
        evidence.capture(CONTEXT, 4, 5, cache=[])
    with pytest.raises(ValueError):
        evidence.resolve(CONTEXT, 4, 5, evidence.capture(CONTEXT, 4, 5), cache=[])
