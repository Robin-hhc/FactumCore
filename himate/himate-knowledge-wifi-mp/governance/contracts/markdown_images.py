"""Recognize Markdown image references without resolving or fetching resources."""

from html import unescape
from html.parser import HTMLParser
import re


_DEFINITION = re.compile(r"^ {0,3}\[([^\]\n]+)\]:[ \t]*(?:<([^>\n]+)>|([^\s]+))", re.MULTILINE)
_START = re.compile(r"!\[|<img\b", re.IGNORECASE)
_HTML_TAG = re.compile(r"""<img\b(?:[^>"']|"[^"]*"|'[^']*')*>""", re.IGNORECASE)
_UNESCAPE = re.compile(r"\\([!-/:-@\[-`{-~])")


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


def markdown_image_tokens(text):
    """Yield (start, end, URI) for inline, reference-style and HTML images."""
    definitions = {}
    for match in _DEFINITION.finditer(text):
        definitions.setdefault(_label(match[1]), _uri(match[2] or match[3]))
    cursor = 0
    while match := _START.search(text, cursor):
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
