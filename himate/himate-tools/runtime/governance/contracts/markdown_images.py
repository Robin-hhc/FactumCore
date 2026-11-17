"""Recognize Markdown image references without resolving or fetching resources."""

from bisect import bisect_right
from html import unescape
from html.parser import HTMLParser
import re

from markdown_it import MarkdownIt
from markdown_it.rules_inline import escape
from markdown_it.rules_inline.backticks import backtick


_DEFINITION = re.compile(r"^ {0,3}\[([^\]\n]+)\]:[ \t]*(?:<([^>\n]+)>|([^\s]+))", re.MULTILINE)
_START = re.compile(r"!\[|<img\b", re.IGNORECASE)
_HTML_TAG = re.compile(r"""<img\b(?:[^>"']|"[^"]*"|'[^']*')*>""", re.IGNORECASE)
_UNESCAPE = re.compile(r"\\([!-/:-@\[-`{-~])")


def _track_literal(rule, state, silent):
    start = state.pos
    count = len(state.tokens)
    matched = rule(state, silent)
    if (matched and not silent and state.src == state.env["literal_source"]
            and (state.src[start:start + 2] in {r"\<", r"\!"}
                 or len(state.tokens) > count and state.tokens[-1].type == "code_inline")):
        state.env["literal_ranges"].append((start, state.pos))
    return matched


_MARKDOWN = MarkdownIt("commonmark")
_MARKDOWN.inline.ruler.at("backticks", lambda state, silent: _track_literal(backtick, state, silent))
_MARKDOWN.inline.ruler.at("escape", lambda state, silent: _track_literal(escape, state, silent))


def _inline_literals(token, lines, offsets, env, *, atx_heading):
    content = token.content
    ranges = []
    _MARKDOWN.inline.parse(content, _MARKDOWN, {**env, "literal_source": content, "literal_ranges": ranges}, [])
    if not ranges:
        return
    fragments = content.split("\n")
    start_line, end_line = token.map
    if len(fragments) != end_line - start_line:
        return
    starts, sources = [0], []
    for line, fragment in enumerate(fragments, start_line):
        original = lines[line]
        if atx_heading:
            original = re.sub(r"[ \t]+#+[ \t]*$", "", original)
        if not original.endswith(fragment):
            original = original.rstrip(" \t")
        sources.append(offsets[line] + len(original) - len(fragment)
                       if original.endswith(fragment) else None)
        starts.append(starts[-1] + len(fragment) + 1)
    for start, stop in ranges:
        for line in range(bisect_right(starts, start) - 1, bisect_right(starts, stop - 1)):
            if sources[line] is not None:
                begin = max(start - starts[line], 0)
                end = min(stop - starts[line], len(fragments[line]))
                yield sources[line] + begin, sources[line] + end


def mask_markdown_literals(text):
    """Blank literal Markdown spans in a scan-only copy without moving source positions."""
    if not _START.search(text):
        return text
    parts = re.split(r"(\r\n?|\n)", text)
    lines = parts[::2]
    offsets = [0]
    for line, separator in zip(lines, parts[1::2]):
        offsets.append(offsets[-1] + len(line) + len(separator))
    offsets.append(len(text))
    tokens, env = [], {}
    _MARKDOWN.block.parse("\n".join(lines), _MARKDOWN, env, tokens)
    ranges = []
    for index, token in enumerate(tokens):
        if token.type in {"fence", "code_block"}:
            start, end = token.map
            ranges.append((offsets[start], min(offsets[end], len(text))))
        elif token.type == "inline" and token.map and _START.search(token.content):
            previous = tokens[index - 1] if index else None
            atx_heading = previous and previous.type == "heading_open" and previous.markup.startswith("#")
            ranges.extend(_inline_literals(token, lines, offsets, env, atx_heading=atx_heading))
    if not ranges:
        return text
    chunks, cursor = [], 0
    for start, end in sorted(ranges):
        start = max(start, cursor)
        if end > start:
            chunks.extend((text[cursor:start], re.sub(r"[^\r\n]", " ", text[start:end])))
            cursor = end
    return "".join((*chunks, text[cursor:]))


def _label(value):
    return " ".join(value.split()).casefold()


def _uri(value):
    return unescape(_UNESCAPE.sub(r"\1", value))


class _ImageTag(HTMLParser):
    source = None

    def handle_starttag(self, tag, attrs):
        if tag == "img":
            self.source = next((value for key, value in attrs if key == "src" and value), None)


def _closing(text, start, opening, closing):
    depth = 1
    escaped = False
    for pos in range(start, len(text)):
        character = text[pos]
        if escaped:
            escaped = False
        elif character == "\\":
            escaped = True
        elif character == opening:
            depth += 1
        elif character == closing:
            depth -= 1
            if depth == 0:
                return pos
    return None


def _destination(text, start):
    pos = start
    while pos < len(text) and text[pos] in " \t\r\n":
        pos += 1
    if text[pos:pos + 1] == "<":
        end = text.find(">", pos + 1)
        if end == -1:
            return None
        value, pos = text[pos + 1:end], end + 1
    else:
        match = re.match(r"(?:\\.|[^\s()\\]|\([^()\n]*\))*", text[pos:])
        value = match[0]
        pos += len(value)
    tail = re.match(r"""\s*(?:(?:"[^"]*"|'[^']*'|\([^()]*\))\s*)?\)""", text[pos:])
    if tail:
        return pos + len(tail[0]), _uri(value)
    return None


def markdown_image_tokens(text, *, masked=None):
    """Yield (start, end, URI) for inline, reference-style and HTML images."""
    masked = mask_markdown_literals(text) if masked is None else masked
    definitions = {}
    for match in _DEFINITION.finditer(masked):
        definitions.setdefault(_label(match[1]), _uri(match[2] or match[3]))
    cursor = 0
    while match := _START.search(masked, cursor):
        start = match.start()
        cursor = match.end()
        if match[0].startswith("<"):
            tag = _HTML_TAG.match(text, start)
            if tag:
                parser = _ImageTag()
                parser.feed(tag[0])
                cursor = tag.end()
                yield start, cursor, parser.source
            continue
        end = _closing(text, cursor, "[", "]")
        if end is None:
            continue
        label = text[cursor:end]
        cursor = end + 1
        if text[cursor:cursor + 1] == "(":
            destination = _destination(text, cursor + 1)
            if destination:
                cursor, reference = destination
                yield start, cursor, reference
                continue
        reference_end = None
        if text[cursor:cursor + 1] == "[":
            reference_end = _closing(text, cursor + 1, "[", "]")
            if reference_end is not None:
                label = text[cursor + 1:reference_end] or label
        reference = definitions.get(_label(label))
        if reference is not None:
            if reference_end is not None:
                cursor = reference_end + 1
            yield start, cursor, reference
