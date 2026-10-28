"""Public symbol navigation over supplied source bytes; no target code executes."""

import hashlib
import importlib.util
from pathlib import Path
import sys

import pytest


DOMAIN = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "code_symbols_contract", DOMAIN / "governance/contracts/__init__.py",
    submodule_search_locations=[str(DOMAIN / "governance/contracts")],
)
contracts = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = contracts
spec.loader.exec_module(contracts)


def symbols():
    return __import__(spec.name + ".code_symbols", fromlist=["resolve"])


def test_function_definition_survives_insertion_and_body_change():
    reference = {"kind": "function", "name": "send"}
    original = b"int send(void) { return 1; }\n"
    changed = b"// inserted line\n\nint send(void) { return 2; }\n"
    before = symbols().resolve(original, reference, path="src/send.c")
    after = symbols().resolve(changed, reference, path="src/send.c")
    assert before["status"] == after["status"] == "resolved"
    assert after["code"] == "CODE_SYMBOL_RESOLVED"
    assert before["range"]["start_line"] == before["range"]["end_line"] == 1
    assert after["range"]["start_line"] == after["range"]["end_line"] == 3
    assert after["path"] == "src/send.c"
    assert after["sha256"] == hashlib.sha256(changed).hexdigest()
    assert after["matches"][0]["name"] == "send"
    assert after["matches"][0]["scope"] == []


@pytest.mark.parametrize("reference", [
    {}, {"kind": "function", "name": ""}, {"kind": "file", "name": "x"},
    {"kind": [], "name": "x"}, {"kind": "function", "name": "x", "language": []},
    {"kind": "macro", "name": "X", "form": []},
    {"kind": "function", "name": "x", "unknown": True},
    {"kind": "function", "name": "x", "scope": "global"},
    {"kind": "function", "name": "x", "parameter_types": [1]},
    {"kind": "function", "name": "x", "qualifiers": ["static"]},
    {"kind": "function", "name": "x", "qualifiers": ["const", "const"]},
    {"kind": "function", "name": "x", "qualifiers": ["&", "&&"]},
    {"kind": "enum", "name": "E", "parameter_types": []},
    {"kind": "macro", "name": "X", "form": "expression"},
    {"kind": "macro", "name": "X", "parameter_count": True},
    {"kind": "macro", "name": "X", "parameter_count": -1},
    {"kind": "macro", "name": "X", "variadic": "yes"},
    {"kind": "macro", "name": "X", "form": "object", "parameter_count": 0},
    {"kind": "macro", "name": "X", "form": "object", "variadic": False},
    {"kind": "struct", "name": "X", "language": "python"},
    {"kind": "function", "name": "x", "role": "any"},
    {"kind": "variable", "name": "x", "role": "declaration"},
    {"kind": "type_alias", "name": "x", "parameter_types": []},
])
def test_invalid_selector_is_a_contract_error(reference):
    with pytest.raises(contracts.ContractError, match="INVALID_CODE_REF"):
        symbols().resolve(b"int x;", reference, path="source.c")


def test_validation_is_read_only_and_accepts_each_supported_shape():
    reference = {"kind": "function", "name": "send", "scope": ["net"],
                 "language": "cpp", "parameter_types": [], "qualifiers": ["const", "&"]}
    original = {**reference, "scope": ["net"], "parameter_types": [], "qualifiers": ["const", "&"]}
    assert symbols().validate_code_ref(reference) is None
    assert reference == original
    for kind in ("struct", "class", "enum", "enum_member"):
        assert symbols().validate_code_ref({"kind": kind, "name": "T"}) is None
    assert symbols().validate_code_ref({"kind": "macro", "name": "LOG", "form": "function",
                                        "parameter_count": 1, "variadic": True}) is None


def test_cpp_overload_selection_uses_scope_parameter_types_and_qualifiers():
    raw = b"""namespace net {
class Host {
 int send(const Packet &packet, int retry = 1) const & { return 1; }
 int send(Packet *packet) && { return 2; }
};
}
int send(int value) { return value; }
"""
    reference = {"kind": "function", "name": "send", "scope": ["net", "Host"],
                 "parameter_types": ["const Packet &", "int"], "qualifiers": ["const", "&"]}
    result = symbols().resolve(raw, reference, path="src/host.cpp")
    assert result["status"] == "resolved"
    assert result["range"]["start_line"] == 3
    assert result["matches"][0]["parameter_types"] == ["const Packet&", "int"]
    assert result["matches"][0]["qualifiers"] == ["const", "&"]
    assert result["matches"][0]["scope"] == ["net", "Host"]
    ambiguous = symbols().resolve(raw, {"kind": "function", "name": "send", "scope": ["net", "Host"]}, path="src/host.cpp")
    assert ambiguous["status"] == "ambiguous" and len(ambiguous["matches"]) == 2
    assert symbols().resolve(raw, {**reference, "parameter_types": ["Packet *"]}, path="src/host.cpp")["status"] == "missing"


def test_c_definitions_exclude_prototypes_and_function_pointer_variables():
    raw = b"""int declared(int value);
int (*callback)(int value);
int send(int (*cb)(int nested), int values[10]) { return cb(1); }
"""
    for name in ("declared", "callback", "nested"):
        assert symbols().resolve(raw, {"kind": "function", "name": name}, path="api.c")["status"] == "missing"
    result = symbols().resolve(raw, {"kind": "function", "name": "send",
                                    "parameter_types": ["int (*)(int)", "int[10]"]}, path="api.c")
    assert result["status"] == "resolved"
    assert result["matches"][0]["parameter_types"] == ["int(*)(int)", "int[10]"]


def test_function_declarations_require_an_explicit_role_and_exclude_pointer_variables():
    raw = b"int send(int value);\nint (*callback)(int);\nint (*factory(void))(double);\nint send(int value) { return value; }\n"
    reference = {"kind": "function", "name": "send", "parameter_types": ["int"]}
    definition = symbols().resolve(raw, reference, path="api.h")
    declaration = symbols().resolve(raw, {**reference, "role": "declaration"}, path="api.h")
    assert definition["status"] == declaration["status"] == "resolved"
    assert definition["matches"][0]["role"] == "definition"
    assert declaration["matches"][0]["role"] == "declaration"
    assert definition["range"]["start_line"] == 4 and declaration["range"]["start_line"] == 1
    assert symbols().resolve(raw, {"kind": "function", "name": "factory", "role": "declaration", "parameter_types": []}, path="api.h")["status"] == "resolved"
    assert symbols().resolve(raw, {"kind": "function", "name": "callback", "role": "declaration"}, path="api.h")["status"] == "missing"


def test_cpp_method_declarations_keep_scope_and_qualifiers():
    raw = b"namespace net { struct Host { int send(const Packet &packet) const &; }; }\n"
    reference = {"kind": "function", "name": "send", "scope": ["net", "Host"],
                 "parameter_types": ["const Packet&"], "qualifiers": ["const", "&"], "role": "declaration"}
    result = symbols().resolve(raw, reference, path="host.hpp")
    assert result["status"] == "resolved"
    assert result["matches"][0]["role"] == "declaration"


def test_typedef_callback_and_global_state_array_have_their_own_symbol_kinds():
    raw = b"typedef unsigned int (*fsm_func)(Host *host, void *param);\nstatic fsm_func states[2][3];\nextern int pending;\nint (*callback)(int);\nint outer(void) { int local; return 0; }\n"
    for kind, name, line in [("type_alias", "fsm_func", 1), ("variable", "states", 2),
                             ("variable", "pending", 3), ("variable", "callback", 4)]:
        result = symbols().resolve(raw, {"kind": kind, "name": name}, path="state.c")
        assert result["status"] == "resolved"
        assert result["range"] == {"start_line": line, "end_line": line}
    assert symbols().resolve(raw, {"kind": "variable", "name": "local", "scope": ["outer"]}, path="state.c")["status"] == "missing"
    assert symbols().resolve(raw, {"kind": "function", "name": "fsm_func", "role": "declaration"}, path="state.c")["status"] == "missing"


def test_type_aliases_include_pointer_multiple_declarators_and_cpp_using():
    raw = b"typedef struct Packet { int value; } Packet, *PacketPtr;\nnamespace net { using Callback = int (*)(int); int state = 0, pending[2]; struct Host { int member; }; }\n"
    for kind, name, scope in [("type_alias", "Packet", []), ("type_alias", "PacketPtr", []),
                              ("type_alias", "Callback", ["net"]), ("variable", "state", ["net"]),
                              ("variable", "pending", ["net"])]:
        assert symbols().resolve(raw, {"kind": kind, "name": name, "scope": scope}, path="types.hpp")["status"] == "resolved"
    assert symbols().resolve(raw, {"kind": "variable", "name": "member", "scope": ["net", "Host"]}, path="types.hpp")["status"] == "missing"


@pytest.mark.parametrize(("raw", "reference", "path"), [
    (b"int (*factory(void))(int) { return 0; }",
     {"kind": "function", "name": "factory", "parameter_types": []}, "factory.c"),
    (b"int (*factory(int (*callback)(int arg)))(double) { return 0; }",
     {"kind": "function", "name": "factory", "parameter_types": ["int(*)(int)"]}, "factory.c"),
    (b"int (*Host::factory() const)(int) { return 0; }",
     {"kind": "function", "name": "factory", "scope": ["Host"],
      "parameter_types": [], "qualifiers": ["const"]}, "factory.cpp"),
])
def test_function_returning_function_pointer_uses_its_own_parameters(raw, reference, path):
    result = symbols().resolve(raw, reference, path=path)
    assert result["status"] == "resolved"
    assert result["matches"][0]["name"] == "factory"
    assert result["matches"][0]["parameter_types"] == reference["parameter_types"]


def test_returned_function_type_cannot_create_a_fake_function_identity():
    result = symbols().resolve(b"int (*factory(void))(int) { return 0; }",
        {"kind": "function", "name": "factory(void)", "parameter_types": ["int"]}, path="factory.c")
    assert result["status"] == "missing" and result["matches"] == []


@pytest.mark.parametrize(("kind", "name", "scope"), [
    ("enum", "Mode", ["Host"]),
    ("enum_member", "READY", ["Host", "Mode"]),
])
def test_anonymous_parent_with_one_direct_typedef_alias_has_a_stable_scope(kind, name, scope):
    raw = b"typedef struct { enum Mode { READY }; } Host;"
    result = symbols().resolve(raw, {"kind": kind, "name": name, "scope": scope}, path="host.cpp")
    assert result["status"] == "resolved"


def test_out_of_line_method_and_parameter_renaming_keep_the_same_identity():
    first = b"int net::Host::send(const Packet &packet, int retry) const & { return 1; }\n"
    second = b"int net::Host::send(const Packet &renamed, int count) const & { return 2; }\n"
    reference = {"kind": "function", "name": "send", "scope": ["net", "Host"],
                 "parameter_types": ["const Packet&", "int"], "qualifiers": ["&", "const"]}
    before = symbols().resolve(first, reference, path="host.cc")
    after = symbols().resolve(second, reference, path="host.cc")
    assert before["status"] == after["status"] == "resolved"
    assert before["matches"] == after["matches"]


def test_cpp17_nested_namespace_uses_one_scope_component_per_namespace():
    compact = b"namespace a::b { int send() { return 1; } }\n"
    expanded = b"namespace a { namespace b { int send() { return 1; } } }\n"
    reference = {"kind": "function", "name": "send", "scope": ["a", "b"]}
    compact_result = symbols().resolve(compact, reference, path="compact.cpp")
    expanded_result = symbols().resolve(expanded, reference, path="expanded.cpp")
    assert compact_result["status"] == expanded_result["status"] == "resolved"
    assert compact_result["matches"] == expanded_result["matches"]


def test_local_class_methods_do_not_share_a_global_class_scope():
    raw = b"int outer() { struct Local { int run() { return 1; } }; return 0; }\n"
    reference = {"kind": "function", "name": "run", "scope": ["outer", "Local"]}
    assert symbols().resolve(raw, reference, path="local.cpp")["status"] == "resolved"
    assert symbols().resolve(raw, {**reference, "scope": ["Local"]}, path="local.cpp")["status"] == "missing"


def test_local_types_and_enum_members_require_the_enclosing_function_scope():
    raw = b"int outer(void) { struct Local { int value; }; enum State { READY }; return 0; }\n"
    for kind, name, suffix in (("struct", "Local", []), ("enum", "State", []), ("enum_member", "READY", ["State"])):
        reference = {"kind": kind, "name": name, "scope": ["outer", *suffix]}
        assert symbols().resolve(raw, reference, path="local.c")["status"] == "resolved"
        assert symbols().resolve(raw, {**reference, "scope": suffix}, path="local.c")["status"] == "missing"


def test_unhandled_cpp_conversion_function_is_explicitly_unavailable():
    raw = b"struct Convert { operator int() const { return 1; } };\n"
    result = symbols().resolve(raw, {"kind": "function", "name": "operator int", "scope": ["Convert"]}, path="convert.cpp")
    assert result["status"] == "unavailable" and result["matches"] == []


@pytest.mark.parametrize(("kind", "name", "scope", "line"), [
    ("struct", "Packet", [], 1), ("struct", "PacketAlias", [], 1),
    ("enum", "State", [], 2), ("enum_member", "READY", ["State"], 2),
    ("enum", "Tagged", [], 3), ("enum", "TagAlias", [], 3),
    ("enum_member", "BUSY", ["TagAlias"], 3),
    ("class", "Host", ["net"], 4), ("enum_member", "READY", ["net", "Host", "Mode"], 4),
])
def test_type_definitions_typedefs_and_enum_members(kind, name, scope, line):
    raw = b"""typedef struct Packet { int length; } PacketAlias;
typedef enum { READY = 1, DONE = READY + 1 } State;
typedef enum Tagged { BUSY } TagAlias;
namespace net { class Host { enum class Mode { READY }; }; }
struct Forward;
class OnlyDeclaration;
"""
    result = symbols().resolve(raw, {"kind": kind, "name": name, "scope": scope}, path="types.hpp")
    assert result["status"] == "resolved"
    assert result["range"]["start_line"] == line
    for forward_kind, forward_name in (("struct", "Forward"), ("class", "OnlyDeclaration")):
        assert symbols().resolve(raw, {"kind": forward_kind, "name": forward_name}, path="types.hpp")["status"] == "missing"


def test_macro_form_fixed_parameters_variadic_and_full_multiline_range():
    raw = b"""// #define FAKE 1
const char *text = "#define FAKE 2";
#define LIMIT 42
#define WRITE(format, ...) \\
 emit(format, __VA_ARGS__)
#define ZERO() 0
"""
    reference = {"kind": "macro", "name": "WRITE", "form": "function", "parameter_count": 1, "variadic": True}
    result = symbols().resolve(raw, reference, path="macros.h")
    assert result["status"] == "resolved"
    assert result["range"] == {"start_line": 4, "end_line": 5}
    match = result["matches"][0]
    assert (match["form"], match["parameter_count"], match["variadic"]) == ("function", 1, True)
    assert symbols().resolve(raw, {"kind": "macro", "name": "LIMIT", "form": "object"}, path="macros.h")["status"] == "resolved"
    assert symbols().resolve(raw, {"kind": "macro", "name": "ZERO", "parameter_count": 0, "variadic": False}, path="macros.h")["status"] == "resolved"
    assert symbols().resolve(raw, {"kind": "macro", "name": "WRITE", "form": "object"}, path="macros.h")["status"] == "missing"
    assert symbols().resolve(raw, {**reference, "parameter_count": 2}, path="macros.h")["status"] == "missing"
    assert symbols().resolve(raw, {"kind": "macro", "name": "FAKE"}, path="macros.h")["status"] == "missing"


def test_conditional_branches_remain_ambiguous_without_assuming_a_build():
    raw = b"#if ENABLED\nint send(void) { return 1; }\n#else\nint send(void) { return 2; }\n#endif\n"
    result = symbols().resolve(raw, {"kind": "function", "name": "send"}, path="send.c")
    assert result["status"] == "ambiguous" and result["code"] == "CODE_SYMBOL_AMBIGUOUS"
    assert [match["range"]["start_line"] for match in result["matches"]] == [2, 4]
    assert "range" not in result


@pytest.mark.parametrize("raw", [b"int broken( {", b"#define LOG(fmt,args...) use(fmt,args)\n", b"int x =\x00;\n"])
def test_parse_errors_are_unavailable_instead_of_missing(raw):
    result = symbols().resolve(raw, {"kind": "function", "name": "absent"}, path="broken.c")
    assert result["status"] == "unavailable"
    assert result["code"] == "CODE_SYMBOL_UNAVAILABLE" and result["matches"] == []
    assert "range" not in result


@pytest.mark.parametrize("raw", [
    b"int broken( {\nint send(void) { return 1; }\n",
    b"int send(void) { return ; broken( }\n",
    b"int send(void) { return 1; }\nint send(int value { return 2; }\n",
])
def test_uncertain_target_or_same_name_region_cannot_prove_a_unique_function(raw):
    result = symbols().resolve(raw, {"kind": "function", "name": "send"}, path="partial.c")
    assert result["status"] == "unavailable"
    assert "range" not in result


def test_unrelated_parse_error_does_not_hide_a_complete_symbol():
    raw = b"int broken(int value { return 0; }\nint send(void) { return 1; }\n"
    result = symbols().resolve(raw, {"kind": "function", "name": "send"}, path="partial.c")
    assert result["status"] == "resolved"
    assert result["range"] == {"start_line": 2, "end_line": 2}
    assert result["partial_parse"] is True
    assert symbols().resolve(raw, {"kind": "function", "name": "absent"}, path="partial.c")["status"] == "unavailable"


def test_return_prefix_identifier_error_preserves_clean_function_identity():
    raw = b"OAL_STATIC uint32_t send(int value) { return value; }\n"
    result = symbols().resolve(raw, {"kind": "function", "name": "send", "parameter_types": ["int"]}, path="decorated.c")
    assert result["status"] == "resolved"
    assert result["partial_parse"] is True
    assert result["matches"][0]["parameter_types"] == ["int"]


def test_decorated_prototype_does_not_make_the_definition_uncertain():
    raw = b"OAL_STATIC uint32_t send(int value);\nOAL_STATIC uint32_t send(int value) { return value; }\n"
    for role, line in [("definition", 2), ("declaration", 1)]:
        result = symbols().resolve(raw, {"kind": "function", "name": "send", "role": role}, path="decorated.c")
        assert result["status"] == "resolved" and result["range"]["start_line"] == line


def test_complete_table_reference_outside_its_error_regions_cannot_hide_a_function():
    raw = b"int send(void){return 1;}\nOAL_STATIC const op table[]={\n{A,send},\n#ifdef ENABLED\n{B,other},\n#endif\n{C,other}\n};\n"
    result = symbols().resolve(raw, {"kind": "function", "name": "send"}, path="table.c")
    assert result["status"] == "resolved"
    assert result["range"] == {"start_line": 1, "end_line": 1}


def test_same_name_syntax_error_inside_an_initializer_remains_uncertain():
    raw = b"int send(void){return 1;}\nint table[]={ int send(void){return 2;} };\n"
    result = symbols().resolve(raw, {"kind": "function", "name": "send"}, path="table.c")
    assert result["status"] == "unavailable"


def test_clean_call_inside_an_unrelated_bad_body_does_not_hide_the_target():
    raw = b"int send(void){return 1;}\nint helper(void) { broken( ; send(); return 0; }\n"
    result = symbols().resolve(raw, {"kind": "function", "name": "send"}, path="calls.c")
    assert result["status"] == "resolved"
    assert symbols().resolve(raw, {"kind": "function", "name": "helper"}, path="calls.c")["status"] == "unavailable"


def test_possible_nested_definition_inside_a_bad_body_keeps_identity_uncertain():
    raw = b"int send(void){return 1;}\nint helper(void) { broken( ; int send(void){return 2;} return 0; }\n"
    result = symbols().resolve(raw, {"kind": "function", "name": "send"}, path="calls.c")
    assert result["status"] == "unavailable"


def test_parse_cache_preserves_selector_independent_uncertainty():
    raw = b"int broken(int value { return 0; }\nint send(void) { return 1; }\n"
    cache = {}
    assert symbols().resolve(raw, {"kind": "function", "name": "send"}, path="partial.c", cache=cache)["status"] == "resolved"
    assert symbols().resolve(raw, {"kind": "function", "name": "broken"}, path="partial.c", cache=cache)["status"] == "unavailable"


def test_gb18030_and_utf8_bom_keep_original_byte_hash_and_physical_lines():
    text = "// 接收聚合帧\r\nint send(int 数量) { return 数量; }\r\n"
    reference = {"kind": "function", "name": "send", "parameter_types": ["int"]}
    for raw, extractor in ((text.encode("gb18030"), "code-gb18030:1"),
                           (b"\xef\xbb\xbf" + text.encode("utf-8"), "code-utf8:1")):
        result = symbols().resolve(raw, reference, path="source.c", extractor=extractor)
        assert result["status"] == "resolved"
        assert result["range"] == {"start_line": 2, "end_line": 2}
        assert result["sha256"] == hashlib.sha256(raw).hexdigest()
    assert symbols().resolve(text.encode("gb18030"), reference, path="source.c")["status"] == "unavailable"
    assert symbols().resolve(b"int send(void) {}", reference, path="source.c", extractor="unknown")["status"] == "unavailable"


def test_parser_dependencies_load_only_for_resolution_and_failure_is_unavailable(monkeypatch):
    import builtins

    original_import = builtins.__import__

    def without_parser(name, *args, **kwargs):
        if name.startswith("tree_sitter"):
            raise ImportError("parser deliberately absent")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", without_parser)
    assert symbols().validate_code_ref({"kind": "struct", "name": "Packet"}) is None
    result = symbols().resolve(b"struct Packet {};", {"kind": "struct", "name": "Packet"}, path="packet.h")
    assert result["status"] == "unavailable" and "parser" in result["reason"].lower()


def test_operation_cache_reuses_parse_but_distinguishes_bytes_and_language(monkeypatch):
    import builtins

    raw = b"int send(void) { return 1; }\n"
    cache = {}
    reference = {"kind": "function", "name": "send"}
    first = symbols().resolve(raw, reference, path="send.c", cache=cache)
    assert first["status"] == "resolved"
    first["matches"][0]["name"] = "tampered-result"
    original_import = builtins.__import__

    def without_parser(name, *args, **kwargs):
        if name.startswith("tree_sitter"):
            raise ImportError("second parse forbidden")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", without_parser)
    second = symbols().resolve(raw, reference, path="renamed.c", cache=cache)
    assert second["status"] == "resolved" and second["matches"][0]["name"] == "send"
    assert second["path"] == "renamed.c"
    assert symbols().resolve(raw + b"// change\n", reference, path="send.c", cache=cache)["status"] == "unavailable"
    assert symbols().resolve(raw, {**reference, "language": "cpp"}, path="send.c", cache=cache)["status"] == "unavailable"
