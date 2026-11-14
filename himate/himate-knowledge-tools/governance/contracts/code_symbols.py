"""Resolve declared symbols from supplied bytes without executing target code."""

from __future__ import annotations

import copy
import hashlib
import importlib.metadata
import re
from pathlib import PurePosixPath

from .validation import ContractError


def validate_code_ref(code_ref):
    """Check selector shape without loading a parser or modifying the selector."""
    if not isinstance(code_ref, dict):
        raise ContractError("INVALID_CODE_REF", "code_ref must be an object")
    kind = code_ref.get("kind")
    if not isinstance(kind, str) or kind not in {"function", "struct", "class", "enum", "enum_member", "macro", "type_alias", "variable"}:
        raise ContractError("INVALID_CODE_REF", "Unsupported symbol kind")
    allowed = {"kind", "name", "scope", "language"}
    if kind == "function":
        allowed |= {"parameter_types", "qualifiers", "role"}
    if kind == "macro":
        allowed |= {"form", "parameter_count", "variadic"}
    if set(code_ref) - allowed:
        raise ContractError("INVALID_CODE_REF", "Fields do not apply to this symbol kind")
    if not isinstance(code_ref.get("name"), str) or not code_ref["name"].strip():
        raise ContractError("INVALID_CODE_REF", "Symbol name must be nonempty text")
    for field in ("scope", "parameter_types", "qualifiers"):
        if field not in code_ref:
            continue
        value = code_ref[field]
        if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
            raise ContractError("INVALID_CODE_REF", field + " must be an array of nonempty strings")
    if "qualifiers" in code_ref and any(item not in {"const", "volatile", "&", "&&"} for item in code_ref["qualifiers"]):
        raise ContractError("INVALID_CODE_REF", "Unknown function qualifier")
    qualifiers = code_ref.get("qualifiers", [])
    if len(set(qualifiers)) != len(qualifiers) or {"&", "&&"}.issubset(qualifiers):
        raise ContractError("INVALID_CODE_REF", "Function qualifiers must be unique and cannot combine & with &&")
    if "language" in code_ref and code_ref["language"] not in ("c", "cpp"):
        raise ContractError("INVALID_CODE_REF", "Unsupported code language")
    if "role" in code_ref and code_ref["role"] not in ("definition", "declaration"):
        raise ContractError("INVALID_CODE_REF", "Unknown function role")
    if "form" in code_ref and code_ref["form"] not in ("object", "function"):
        raise ContractError("INVALID_CODE_REF", "Unknown macro form")
    if "parameter_count" in code_ref and (type(code_ref["parameter_count"]) is not int or code_ref["parameter_count"] < 0):
        raise ContractError("INVALID_CODE_REF", "Macro parameter_count must be a nonnegative integer")
    if "variadic" in code_ref and type(code_ref["variadic"]) is not bool:
        raise ContractError("INVALID_CODE_REF", "Macro variadic must be boolean")
    if code_ref.get("form") == "object" and {"parameter_count", "variadic"} & set(code_ref):
        raise ContractError("INVALID_CODE_REF", "Object macro selectors cannot specify function parameters")


def _range(node):
    end = node.end_point.row + 1
    if node.end_point.column == 0 and node.end_byte > node.start_byte:
        end -= 1
    return {"start_line": node.start_point.row + 1, "end_line": end}


def _walk(node):
    yield node
    for child in node.named_children:
        yield from _walk(child)


def _text(node, source):
    return source[node.start_byte:node.end_byte].decode("utf-8")


def _type_text(value):
    """Normalize token spacing only; aliases and type semantics remain distinct."""
    value = re.sub(r"/\*.*?\*/|//[^\r\n]*", " ", value, flags=re.S)
    tokens = re.findall(r"::|&&|\.\.\.|\w+|[^\s]", value)
    output = ""
    for token in tokens:
        if output and (output[-1].isalnum() or output[-1] == "_") and (token[0].isalnum() or token[0] == "_"):
            output += " "
        output += token
    return output


def _qualified(node, source):
    if node is None:
        return []
    if node.type == "nested_namespace_specifier":
        return [name for child in node.named_children for name in _qualified(child, source)]
    if node.type == "qualified_identifier":
        return _qualified(node.child_by_field_name("scope"), source) + _qualified(node.child_by_field_name("name"), source)
    return [_type_text(_text(node, source))]


def _function_declarator(node):
    return _selected_function(node.child_by_field_name("declarator"))


def _selected_function(declarator):
    selected = None
    while declarator is not None:
        if declarator.type == "function_declarator":
            selected = declarator
        following = declarator.child_by_field_name("declarator")
        if following is None and declarator.type in {"parenthesized_declarator", "reference_declarator"}:
            children = [child for child in declarator.named_children if child.type != "comment"]
            following = children[0] if len(children) == 1 else None
        declarator = following
    return selected


def _declarator_name(declarator):
    name = declarator.child_by_field_name("declarator")
    while name is not None and name.type in {"pointer_declarator", "parenthesized_declarator", "reference_declarator"}:
        name = name.child_by_field_name("declarator") or next(iter(name.named_children), None)
    return name


def _scope(node, source):
    scopes = []
    parent = node.parent
    while parent is not None:
        if parent.type in {"namespace_definition", "class_specifier", "struct_specifier", "union_specifier"}:
            name = parent.child_by_field_name("name")
            if name is None and parent.parent is not None and parent.parent.type == "type_definition":
                aliases = [child for child in parent.parent.children_by_field_name("declarator")
                           if child.type == "type_identifier"]
                if len(aliases) == 1:
                    name = aliases[0]
            scopes.append(_qualified(name, source) if name is not None else ["<anonymous>"])
        elif parent.type == "function_definition":
            declarator = _function_declarator(parent)
            if declarator is not None:
                scopes.append(_qualified(_declarator_name(declarator), source))
        elif parent.type == "lambda_expression":
            scopes.append(["<lambda>"])
        parent = parent.parent
    return [name for scope in reversed(scopes) for name in scope]


def _parameter_names(node):
    """Find declarator names, including names inside function-pointer parameters."""
    if node is None:
        return []
    if node.type in {"identifier", "field_identifier"}:
        return [(node.start_byte, node.end_byte)]
    spans = []
    declarator = node.child_by_field_name("declarator")
    if declarator is not None:
        spans += _parameter_names(declarator)
    elif node.type in {"reference_declarator", "parenthesized_declarator"}:
        for child in node.named_children:
            spans += _parameter_names(child)
    parameters = node.child_by_field_name("parameters")
    if parameters is not None:
        for parameter in parameters.named_children:
            spans += _parameter_names(parameter.child_by_field_name("declarator"))
    return spans


def _parameter_type(node, source):
    stop = node.end_byte
    default = node.child_by_field_name("default_value")
    if default is not None:
        stop = next(child.start_byte for child in node.children if child.type == "=")
    raw = bytearray(source[node.start_byte:stop])
    for start, end in _parameter_names(node.child_by_field_name("declarator")):
        raw[start - node.start_byte:end - node.start_byte] = b" " * (end - start)
    return _type_text(raw.decode("utf-8"))


def _function(node, source, *, declarator=None, role="definition"):
    declarator = declarator or _function_declarator(node)
    if declarator is None:
        raise ValueError("Unsupported function declarator; its identity cannot be established")
    name_node = _declarator_name(declarator)
    if name_node is None or name_node.type not in {
            "identifier", "field_identifier", "qualified_identifier", "destructor_name", "operator_name"}:
        raise ValueError("Function declarator has no reliable symbol name")
    names = _qualified(name_node, source)
    parameters = declarator.child_by_field_name("parameters")
    if parameters is None:
        raise ValueError("Function declarator has no reliable parameter structure")
    types = [_parameter_type(child, source) for child in parameters.named_children if child.type != "comment"]
    if types == ["void"]:
        types = []
    qualifiers = [_text(child, source) for child in declarator.named_children
                  if child.type in {"type_qualifier", "ref_qualifier"} and _text(child, source) in {"const", "volatile", "&", "&&"}]
    return {"kind": "function", "name": names[-1], "scope": _scope(node, source) + names[:-1],
            "parameter_types": types, "qualifiers": [item for item in ("const", "volatile", "&", "&&") if item in qualifiers],
            "role": role, "range": _range(node)}


def _matches(symbol, reference):
    if (symbol["kind"], symbol["name"], symbol["scope"]) != (reference["kind"], reference["name"], reference.get("scope", [])):
        return False
    if symbol["kind"] == "function" and symbol["role"] != reference.get("role", "definition"):
        return False
    if "parameter_types" in reference and symbol.get("parameter_types") != [_type_text(item) for item in reference["parameter_types"]]:
        return False
    if "qualifiers" in reference and sorted(symbol.get("qualifiers", [])) != sorted(reference["qualifiers"]):
        return False
    for field in ("form", "parameter_count", "variadic"):
        if field in reference and symbol.get(field) != reference[field]:
            return False
    return True


def _aggregate(node, source):
    body = node.child_by_field_name("body")
    if body is None:
        return []
    kind = {"struct_specifier": "struct", "class_specifier": "class", "enum_specifier": "enum"}[node.type]
    names = []
    name = node.child_by_field_name("name")
    if name is not None:
        names.append((_text(name, source), node))
    parent = node.parent
    if parent is not None and parent.type == "type_definition":
        for alias in parent.children_by_field_name("declarator"):
            if alias.type == "type_identifier" and all(existing != _text(alias, source) for existing, _ in names):
                names.append((_text(alias, source), parent))
    matches = []
    scope = _scope(node, source)
    for name, extent in names:
        matches.append({"kind": kind, "name": name, "scope": list(scope), "range": _range(extent)})
        if kind == "enum":
            for child in _walk(body):
                if child.type == "enumerator":
                    member = child.child_by_field_name("name")
                    matches.append({"kind": "enum_member", "name": _text(member, source),
                                    "scope": [*scope, name], "range": _range(child)})
    return matches


def _macro(node, source):
    parameters = node.child_by_field_name("parameters")
    return {"kind": "macro", "name": _text(node.child_by_field_name("name"), source), "scope": [],
            "form": "object" if parameters is None else "function",
            "parameter_count": 0 if parameters is None else sum(child.type == "identifier" for child in parameters.named_children),
            "variadic": parameters is not None and any(child.type == "..." for child in parameters.children),
            "range": _range(node)}


def _leaf_declarator(node):
    while node is not None:
        if node.type in {"identifier", "field_identifier", "type_identifier", "qualified_identifier"}:
            return node
        following = node.child_by_field_name("declarator")
        if following is None and node.type in {"parenthesized_declarator", "reference_declarator"}:
            children = [child for child in node.named_children if child.type != "comment"]
            following = children[0] if len(children) == 1 else None
        node = following
    raise ValueError("Declarator has no reliable symbol name")


def _declarations(node, source):
    symbols = []
    parent = node.parent
    file_variable = node.type == "declaration"
    while parent is not None:
        if parent.type in {"function_definition", "lambda_expression", "class_specifier", "struct_specifier", "union_specifier"}:
            file_variable = False
        parent = parent.parent
    for declarator in node.children_by_field_name("declarator"):
        function = _selected_function(declarator)
        # A pointer wrapping the callable's name declares a variable, whereas a
        # function returning a pointer has its own inner function_declarator.
        name = function.child_by_field_name("declarator") if function is not None else None
        if name is not None and name.type in {"identifier", "field_identifier", "qualified_identifier", "destructor_name", "operator_name"}:
            symbols.append(_function(node, source, declarator=function, role="declaration"))
        elif file_variable:
            names = _qualified(_leaf_declarator(declarator), source)
            symbols.append({"kind": "variable", "name": names[-1], "scope": _scope(node, source) + names[:-1],
                            "range": _range(node)})
    return symbols


def _aliases(node, source):
    declarators = node.children_by_field_name("declarator") if node.type == "type_definition" else [node.child_by_field_name("name")]
    symbols = []
    for declarator in declarators:
        names = _qualified(_leaf_declarator(declarator), source)
        symbols.append({"kind": "type_alias", "name": names[-1], "scope": _scope(node, source) + names[:-1],
                        "range": _range(node)})
    return symbols


def _symbols(tree, source):
    symbols = []
    uncertain = []
    for node in _walk(tree.root_node):
        parent = node.parent
        inside_error = False
        while parent is not None:
            inside_error |= parent.type == "ERROR" or parent.is_missing
            parent = parent.parent
        if inside_error or (node.has_error and not _safe_function_prefix(node, source)):
            if node.type in {"function_definition", "declaration", "field_declaration", "type_definition", "alias_declaration",
                             "struct_specifier", "class_specifier", "enum_specifier", "preproc_def", "preproc_function_def"}:
                uncertain.extend(_identity_regions(node, source))
            continue
        try:
            if node.type == "function_definition":
                symbols.append(_function(node, source))
            elif node.type in {"struct_specifier", "class_specifier", "enum_specifier"}:
                symbols.extend(_aggregate(node, source))
            elif node.type in {"preproc_def", "preproc_function_def"}:
                symbols.append(_macro(node, source))
            elif node.type in {"declaration", "field_declaration"}:
                symbols.extend(_declarations(node, source))
            elif node.type in {"type_definition", "alias_declaration"}:
                symbols.extend(_aliases(node, source))
        except (ValueError, TypeError):
            uncertain.append(_text(node, source))
    for error in _syntax_errors(tree.root_node):
        region = error
        parent = error.parent
        while parent is not None and parent.type != "translation_unit":
            if parent.type in {"function_definition", "declaration", "field_declaration", "type_definition",
                               "alias_declaration", "preproc_def", "preproc_function_def"}:
                region = parent
                break
            region = parent
            parent = parent.parent
        if _safe_function_prefix(region, source) or _bounded_initializer_error(error, region, source):
            # Only the isolated prefix identifier is uncertain; the function's
            # name, parameter list, and body are structurally complete.
            region = error
        elif _bounded_function_body(error, region):
            uncertain.extend(_identity_regions(region, source, descendants=True))
            region = error
        uncertain.append(_text(region, source))
    return symbols, uncertain, tree.root_node.has_error or bool(uncertain)


def _syntax_errors(node):
    if node.type == "ERROR" or node.is_missing:
        yield node
    for child in node.children:
        yield from _syntax_errors(child)


def _identity_regions(node, source, *, descendants=False):
    for item in _walk(node) if descendants else [node]:
        if item.type not in {"function_definition", "declaration", "field_declaration", "type_definition", "alias_declaration",
                             "struct_specifier", "class_specifier", "enum_specifier", "preproc_def", "preproc_function_def"}:
            continue
        for declarator in item.children_by_field_name("declarator"):
            if declarator.type == "init_declarator":
                declarator = declarator.child_by_field_name("declarator")
            if declarator is not None:
                yield _text(declarator, source)
        name = item.child_by_field_name("name")
        if name is not None:
            yield _text(name, source)


def _bounded_function_body(error, node):
    if node.type != "function_definition":
        return False
    declarator = node.child_by_field_name("declarator")
    body = node.child_by_field_name("body")
    return (declarator is not None and not declarator.has_error and body is not None
            and bool(body.children) and body.children[0].type == "{" and not body.children[0].is_missing
            and body.children[-1].type == "}" and not body.children[-1].is_missing
            and body.start_byte <= error.start_byte and error.end_byte <= body.end_byte)


def _safe_function_prefix(node, source):
    """Allow only isolated decorator/return-type identifiers before a clean signature."""
    if node.type not in {"function_definition", "declaration", "field_declaration"}:
        return False
    declarator = node.child_by_field_name("declarator")
    body = node.child_by_field_name("body")
    if declarator is None or declarator.has_error:
        return False
    if node.type == "function_definition" and (body is None or body.has_error):
        return False
    if node.type != "function_definition" and (not node.children or node.children[-1].type != ";" or node.children[-1].is_missing):
        return False
    function = _selected_function(declarator)
    name = function.child_by_field_name("declarator") if function is not None else None
    if name is None or name.type not in {"identifier", "field_identifier", "qualified_identifier", "destructor_name", "operator_name"}:
        return False
    errors = list(_syntax_errors(node))
    return bool(errors) and all(not error.is_missing and error.type == "ERROR"
                               and error.end_byte <= declarator.start_byte
                               and re.fullmatch(r"[^\W\d]\w*", _text(error, source), flags=re.UNICODE)
                               for error in errors)


def _bounded_initializer_error(error, declaration, source):
    """Do not widen a table's isolated errors to its otherwise parsed references."""
    if declaration.type != "declaration" or not declaration.children:
        return False
    if declaration.children[-1].type != ";" or declaration.children[-1].is_missing:
        return False
    declarators = declaration.children_by_field_name("declarator")
    if not declarators:
        return False
    for declarator in declarators:
        if declarator.type != "init_declarator":
            return False
        binding = declarator.child_by_field_name("declarator")
        value = declarator.child_by_field_name("value")
        if binding is None or binding.has_error or value is None or value.type != "initializer_list":
            return False
        if not value.children or value.children[-1].type != "}" or value.children[-1].is_missing:
            return False
        if value.start_byte <= error.start_byte and error.end_byte <= value.end_byte:
            return True
    return (not error.is_missing and error.end_byte <= declarators[0].start_byte
            and bool(re.fullmatch(r"[^\W\d]\w*", _text(error, source), flags=re.UNICODE)))


def _guarded_linkage_view(source):
    """Mask paired standalone C++ linkage boundaries, preserving byte offsets.

    Tree-sitter sees both preprocessor branches before preprocessing. A common
    header's separately guarded ``extern "C" {`` and ``}`` can therefore absorb
    the whole file into an ERROR node in either grammar. Only canonical paired
    __cplusplus guards qualify; all declarations, branches and other errors
    remain in the full-file parse. This view never replaces original evidence.
    """
    ending = rb"[ \t]*(?:/\*[^\r\n]*\*/[ \t]*)?\r?\n"
    opening = rb"[ \t]*#[ \t]*ifdef[ \t]+__cplusplus" + ending
    nested = rb"[ \t]*#[ \t]*if[ \t]+__cplusplus" + ending
    closing = rb"[ \t]*#[ \t]*endif" + ending
    boundary = rb"(?P<boundary>[ \t]*(?:extern[ \t]+\"C\"[ \t]*\{|})[ \t]*)\r?\n"
    events = []
    for depth in (1, 2):
        pattern = opening + nested * (depth - 1) + boundary + closing * depth
        for match in re.finditer(rb"^" + pattern, source, flags=re.M):
            events.append((match.start(), depth, match.group("boundary").strip().startswith(b"extern"),
                           match.span("boundary")))
    stack, spans = [], []
    for _, depth, is_open, span in sorted(events):
        if is_open:
            stack.append((depth, span))
        elif not stack or stack[-1][0] != depth:
            return source  # An unpaired or mixed wrapper cannot be normalized.
        else:
            _, first = stack.pop()
            spans.extend((first, span))
    if stack or not spans:
        return source
    view = bytearray(source)
    for start, end in spans:
        view[start:end] = b" " * (end - start)
    return bytes(view)


def _parse(data, language, extractor):
    codecs = {None: "utf-8-sig", "code-utf8:1": "utf-8-sig", "code-gb18030:1": "gb18030"}
    if extractor not in codecs:
        return [], "The declared code extraction adapter is unavailable", [], False
    try:
        text = data.decode(codecs[extractor], errors="strict")
        if "\0" in text:
            return [], "NUL bytes prevent reliable source parsing", [], False
        source = _guarded_linkage_view(text.encode("utf-8"))
        # Importing this shared module never requires a parser installation.
        from tree_sitter import Language, Parser
        if language == "cpp":
            import tree_sitter_cpp as grammar
        else:
            import tree_sitter_c as grammar
        tree = Parser(Language(grammar.language())).parse(source)
        symbols, uncertain, partial = _symbols(tree, source)
        return symbols, None, uncertain, partial
    except (ImportError, OSError, ValueError, TypeError, RuntimeError, RecursionError) as exc:
        return [], "Source parser unavailable: " + str(exc), [], False


def resolve(data, code_ref, *, path, extractor=None, cache=None):
    """Return a navigation observation; source bytes remain the caller's evidence."""
    validate_code_ref(code_ref)
    if not isinstance(data, bytes) or not isinstance(path, str) or not path or "\0" in path:
        raise ContractError("INVALID_CODE_REF", "Source bytes and a nonempty source path are required")
    if cache is not None and not isinstance(cache, dict):
        raise ContractError("INVALID_CODE_REF", "Operation cache must be an object")
    digest = hashlib.sha256(data).hexdigest()
    language = code_ref.get("language", "cpp" if PurePosixPath(path).suffix.lower() in {".cpp", ".hpp", ".cc", ".cxx", ".hxx", ".hh", ".c++"} else "c")
    parsed, problem, uncertain, partial = [], None, [], False
    try:
        grammar = "tree-sitter-cpp" if language == "cpp" else "tree-sitter-c"
        key = ("code-symbols:3", digest, language, extractor or "code-utf8:1",
               importlib.metadata.version("tree-sitter"), importlib.metadata.version(grammar))
        if cache is not None and key in cache:
            parsed, problem, uncertain, partial = cache[key]
        else:
            parsed, problem, uncertain, partial = _parse(data, language, extractor)
            if cache is not None:
                cache[key] = (parsed, problem, uncertain, partial)
    except importlib.metadata.PackageNotFoundError as exc:
        problem = "Source parser dependency unavailable: " + str(exc)
    matches = copy.deepcopy([symbol for symbol in parsed if _matches(symbol, code_ref)])
    if not problem and uncertain and (not matches or any(code_ref["name"] in region for region in uncertain)):
        problem = "Source contains uncertain syntax for this symbol; uniqueness or absence cannot be established"
    status = "unavailable" if problem else "resolved" if len(matches) == 1 else "ambiguous" if matches else "missing"
    identity = "::".join([*code_ref.get("scope", []), code_ref["name"]])
    result = {"status": status, "code": "CODE_SYMBOL_" + status.upper(),
              "reason": problem or f"{code_ref['kind']} {identity}: symbol lookup {status}", "path": path,
              "sha256": digest, "matches": matches}
    if partial:
        result["partial_parse"] = True
    if status == "resolved":
        result["range"] = dict(matches[0]["range"])
    return result
