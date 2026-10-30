"""Guard-split C linkage boundaries must not hide or invent header symbols."""

import hashlib
import importlib.util
from pathlib import Path

import pytest


_spec = importlib.util.spec_from_file_location(
    "guarded_linkage_support", Path(__file__).resolve().parents[1] / "support/contracts.py")
_support = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_support)
module = _support.module


def header(body, nested=True):
    before = '#ifdef __cplusplus\n' + ('#if __cplusplus\n' if nested else '')
    after = '#endif\n' * (2 if nested else 1)
    return '#ifndef SAMPLE_H\n#define SAMPLE_H\n' + before + 'extern "C" {\n' + after + body + before + '}\n' + after + '#endif\n'


@pytest.mark.parametrize("language", ["c", "cpp"])
@pytest.mark.parametrize("nested", [False, True])
def test_guarded_linkage_preserves_real_symbol_range_and_original_digest(language, nested):
    raw = header('static int ready(int value) { return value; }\n', nested).encode()
    result = module("code_symbols").resolve(raw, {"kind": "function", "name": "ready", "language": language}, path="sample.h")
    assert result["status"] == "resolved", result
    line = 8 if nested else 6
    assert result["range"] == {"start_line": line, "end_line": line}
    assert result["sha256"] == hashlib.sha256(raw).hexdigest()
    assert result["matches"][0]["parameter_types"] == ["int"]


@pytest.mark.parametrize("body", [
    'int ready(int value) { return value; }\nint ready(int value) { return value + 1; }\n',
    '#if FEATURE_A\nint ready(int value) { return value; }\n#else\nint ready(int value) { return value + 1; }\n#endif\n',
])
def test_guarded_linkage_keeps_duplicate_definitions_ambiguous(body):
    result = module("code_symbols").resolve(header(body).encode(), {"kind": "function", "name": "ready"}, path="sample.h")
    assert result["status"] == "ambiguous", result
    assert len(result["matches"]) == 2


def test_guarded_linkage_does_not_accept_the_wrong_signature():
    result = module("code_symbols").resolve(header('int ready(int value) { return value; }\n').encode(),
        {"kind": "function", "name": "ready", "parameter_types": ["double"]}, path="sample.h")
    assert result["status"] == "missing", result


def test_guarded_linkage_does_not_hide_a_damaged_same_name_signature():
    raw = header('int ready(int value) { return value; }\nint ready(int broken\n').encode()
    result = module("code_symbols").resolve(raw, {"kind": "function", "name": "ready"}, path="sample.h")
    assert result["status"] == "unavailable", result


@pytest.mark.parametrize("container", ["comment", "raw-string"])
def test_wrapper_text_in_comments_or_strings_cannot_create_a_symbol(container):
    quoted = header('int decoy(void) { return 0; }\n')
    raw = ('/*\n' + quoted + '*/\n' if container == 'comment'
           else 'const char *manual = R"DOC(\n' + quoted + ')DOC";\n')
    raw = (raw + 'int ready(void) { return 1; }\n').encode()
    symbols = module("code_symbols")
    assert symbols.resolve(raw, {"kind": "function", "name": "decoy", "language": "cpp"}, path="sample.hpp")["status"] == "missing"
    assert symbols.resolve(raw, {"kind": "function", "name": "ready", "language": "cpp"}, path="sample.hpp")["status"] == "resolved"
