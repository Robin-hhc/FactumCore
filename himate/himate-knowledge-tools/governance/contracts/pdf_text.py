"""Conservatively classify printed PDF margin line numbers as furniture.

The original text and provenance remain in the document.  Callers must retain
element locators separately when excluding furniture from reading materials.
"""
from __future__ import annotations

from collections import defaultdict
import math
from statistics import median

_PROTECTED = frozenset({
    "table", "picture", "chart", "code", "list_item", "list", "ordered_list",
    "document_index", "picture_area",
})


def _finite(values):
    return all(isinstance(value, (int, float)) and not isinstance(value, bool)
               and math.isfinite(value) for value in values)


def _protected_nodes(document):
    nodes = {node.self_ref: node for collection in (
        document.texts, document.tables, document.pictures, document.groups,
        [document.body],
    ) for node in collection}
    protected = {}

    def check(node):
        path, seen = [], set()
        while node.self_ref not in protected:
            reference = node.self_ref
            if reference in seen:
                blocked = True
                break
            seen.add(reference)
            path.append(reference)
            if node.label in _PROTECTED:
                blocked = True
                break
            if node.parent is None:
                blocked = False
                break
            parent = nodes.get(node.parent.cref)
            if parent is None:
                blocked = True
                break
            node = parent
        else:
            blocked = protected[node.self_ref]
        for reference in path:
            protected[reference] = blocked
        return blocked

    return {item.self_ref for item in document.texts if check(item)}


def _page_boxes(document):
    """Normalize valid geometry once; unknown or invalid geometry is retained."""
    sizes = {}
    for number, page in document.pages.items():
        width, height = page.size.width, page.size.height
        if _finite((width, height)) and width > 0 and height > 0:
            sizes[number] = (width, height)
    pages = defaultdict(list)
    for collection in (document.texts, document.tables, document.pictures):
        for item in collection:
            for provenance in item.prov:
                size = sizes.get(provenance.page_no)
                if size is None:
                    continue
                width, height = size
                original = provenance.bbox
                if (original.coord_origin not in {"TOPLEFT", "BOTTOMLEFT"}
                        or not _finite((original.l, original.t, original.r, original.b))):
                    continue
                box = original.to_top_left_origin(page_height=height)
                if not (0 <= box.l < box.r <= width and 0 <= box.t < box.b <= height):
                    continue
                pages[provenance.page_no].append((item, box))
    return sizes, pages


def _sequence(rows, height):
    rows.sort(key=lambda row: row[1].t)
    if len(rows) < 20:
        return None
    numbers = [int(item.text.strip()) for item, _ in rows]
    if numbers[0] > 3 or numbers != list(range(numbers[0], numbers[0] + len(numbers))):
        return None
    boxes = [box for _, box in rows]
    if boxes[-1].b - boxes[0].t < height * .5:
        return None
    letter_height = median(box.b - box.t for box in boxes)
    tolerance = max(1.5, letter_height * .35)
    if min(max(box.l for box in boxes) - min(box.l for box in boxes),
           max(box.r for box in boxes) - min(box.r for box in boxes)) > tolerance:
        return None
    pitches = [right.t - left.t for left, right in zip(boxes, boxes[1:])]
    pitch = median(pitches)
    if min(pitches) <= 0 or max(abs(value - pitch) for value in pitches) > pitch * .2:
        return None
    return boxes[0].t, boxes[-1].b, pitch, max(12, letter_height * 1.5)


def _separate_from_body(rows, records, side, sequence, body_layer):
    top, bottom, pitch, clearance = sequence
    selected = {item.self_ref for item, _ in rows}
    left = min(box.l for _, box in rows)
    right = max(box.r for _, box in rows)
    body_lines = 0
    for item, box in records:
        if item.self_ref in selected:
            continue
        # A table heading, nearby list text, or a diagram crossing this strip
        # makes the interpretation ambiguous, even just above/below the run.
        if box.b >= top - 2 * pitch and box.t <= bottom + 2 * pitch:
            if box.l <= right and box.r >= left:
                return False
        if box.b <= top or box.t >= bottom:
            continue
        gap = box.l - right if side == "left" else left - box.r
        if gap < clearance:
            return False
        text = getattr(item, "text", "").strip()
        if item.content_layer == body_layer and len(text) >= 8 and not text.isdigit():
            body_lines += 1
    return body_lines >= max(10, len(rows) // 3)


def mark_margin_line_numbers(document) -> set[str]:
    """Mark only long, isolated, aligned margin sequences; return changed refs.

    Short/irregular runs, merged text cells and uncertain structures are left
    alone.  A semantic list with exactly the same unlabelled geometry remains
    inherently ambiguous; no claim of general layout understanding is made.
    """
    from docling_core.types.doc import ContentLayer, DocItemLabel

    sizes, pages = _page_boxes(document)
    protected = _protected_nodes(document)
    changed = set()
    for number, records in pages.items():
        width, height = sizes[number]
        sides = defaultdict(list)
        for item, box in records:
            text = getattr(item, "text", "").strip()
            if (item.self_ref in protected or item.label != DocItemLabel.TEXT
                    or item.content_layer != ContentLayer.BODY or len(item.prov) != 1
                    or not text.isascii() or not text.isdigit() or len(text) > 3
                    or text.startswith("0") or not 1 <= int(text) <= 999
                    or box.r - box.l > width * .025 or box.b - box.t > height * .04):
                continue
            side = "left" if box.r <= width * .1 else "right" if box.l >= width * .9 else None
            if side is not None:
                sides[side].append((item, box))
        for side, rows in sides.items():
            sequence = _sequence(rows, height)
            if sequence is None or not _separate_from_body(rows, records, side, sequence, ContentLayer.BODY):
                continue
            for item, _ in rows:
                item.content_layer = ContentLayer.FURNITURE
                changed.add(item.self_ref)
    return changed
