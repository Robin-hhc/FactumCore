"""Bound consecutive reads of the one fixed Markdown document."""

from bisect import bisect_right
from pathlib import PurePosixPath
import re

from . import document_material, document_parser
from .catalog import normalize_page_ranges, remaining_page_ranges
from .validation import ContractError, canonical_bytes, sha256_bytes


MAX_REVIEW_BYTES = 76_000
PACKET = ".build/materials/document-review.md"
INDEX = ".build/materials/document-review.json"
_HEADING = re.compile(rb"(?m)^#{1,6} ([^\r\n]+)\n")


def _pieces(content, start, end, size):
    while start < end:
        stop = min(start + size, end)
        if stop < end:
            line_end = content.rfind(b"\n", start + size // 2, stop)
            if line_end != -1:
                stop = line_end + 1
            while (content[stop] & 0xC0) == 0x80:
                stop -= 1
        yield start, stop
        start = stop


def units(markdown, suffix, pages):
    if suffix == ".pdf":
        markers = list(document_material.PAGE_MARKER.finditer(markdown))
        if not markers or [int(mark.group(1)) for mark in markers] != pages:
            raise ContractError("DOCUMENT_REVIEW_PAGE_MAP", "Markdown must identify every physical source page")
        starts = [0, *(mark.start() for mark in markers[1:]), len(markdown)]
        for page, start, end in zip(pages, starts, starts[1:]):
            yield from ({"start": first, "end": last, "page": page}
                        for first, last in _pieces(markdown, start, end, MAX_REVIEW_BYTES))
    else:
        # Office units preserve Markdown line/row boundaries and point to the
        # Word heading or Excel sheet heading in the canonical document.
        headings = list(_HEADING.finditer(markdown))
        offsets = [heading.start() for heading in headings]
        lines = [position for position, byte in enumerate(markdown) if byte == 10]
        for start, end in _pieces(markdown, 0, len(markdown), 2_000):
            section = bisect_right(offsets, start) - 1
            entry = {"start": start, "end": end, "start_line": bisect_right(lines, start - 1) + 1,
                     "end_line": bisect_right(lines, end - 2) + 1}
            if section >= 0:
                entry["section"] = headings[section].group(1).decode("utf-8")
            yield entry


def _reviewed(source, identity, entries):
    progress = source.get("processing") or {}
    if source["change"] == "reprocess" or progress.get("source_sha256") != source["hash"]:
        return []
    if progress.get("review_sha256", identity) != identity:
        return []
    if "reviewed_units" in progress:
        return normalize_page_ranges(progress["reviewed_units"], len(entries))
    old_pages = progress.get("reviewed_pages", [])
    reviewed = [[i, i] for i, entry in enumerate(entries, 1)
                if any(first <= entry.get("page", 0) <= last for first, last in old_pages)]
    return normalize_page_ranges(reviewed, len(entries))


def material(source, loaded, text_budget, page_budget):
    """Return the candidate and index without rewriting source bytes or image markup."""
    markdown = loaded["markdown"].encode("utf-8")
    suffix = PurePosixPath(source["path"]).suffix.lower()
    entries = list(units(markdown, suffix, loaded["manifest"]["pages"]))
    if not entries:
        raise ContractError("DOCUMENT_REVIEW_EMPTY", "The completed document has no readable Markdown")
    identity = sha256_bytes(canonical_bytes({"content": sha256_bytes(markdown), "layout": 1}))
    reviewed = _reviewed(source, identity, entries)
    remaining = remaining_page_ranges(len(entries), reviewed)
    if not remaining:
        raise ContractError("DOCUMENT_REVIEW_ALREADY_COMPLETE", "No unreviewed material remains")
    first, last = remaining[0]
    start = entries[first - 1]["start"]
    # A legacy smaller soft threshold can always advance by one indivisible unit.
    budget = max(min(text_budget, MAX_REVIEW_BYTES), entries[first - 1]["end"] - start)
    first_page = entries[first - 1].get("page")
    end = first
    for number in range(first + 1, last + 1):
        entry = entries[number - 1]
        if (entry["end"] - start > budget
                or page_budget is not None and first_page is not None and entry["page"] >= first_page + page_budget):
            break
        end = number
    packet = markdown[start:entries[end - 1]["end"]]
    scope = {"review_sha256": identity, "start_unit": first, "end_unit": end,
             "total_units": len(entries), "reviewed_units": reviewed, "remaining_units": remaining,
             "text_budget": budget, "text_bytes": len(packet), "page_budget": page_budget,
             "packet_ref": PACKET, "index_ref": INDEX, "markdown_ref": loaded["manifest"]["markdown_ref"]}
    index = {"scope": scope, "units": [{"unit": number, **entries[number - 1]} for number in range(first, end + 1)]}
    return scope, index, packet, entries


def prepare(root, source, loaded, text_budget, page_budget):
    scope, index, packet, entries = material(source, loaded, text_budget, page_budget)
    document_parser.safe_path(root, PACKET, [".build/materials"]).write_bytes(packet)
    document_parser.safe_path(root, INDEX, [".build/materials"]).write_bytes(canonical_bytes(index))
    return scope, _pdf_scope(scope, entries)


def _pdf_scope(scope, entries):
    # Page-based consumers may still use the same range when each unit is a whole page.
    if any(entry.get("page") != number for number, entry in enumerate(entries, 1)):
        return None
    return {"total_pages": scope["total_units"], "start_page": scope["start_unit"], "end_page": scope["end_unit"],
            "reviewed_pages": scope["reviewed_units"], "remaining_pages": scope["remaining_units"],
            "page_budget": scope["page_budget"], "text_budget": scope["text_budget"], "text_units": scope["text_bytes"],
            "packet_ref": PACKET, "page_index_ref": INDEX}


def validate(root, task, plan, loaded):
    recorded = task.get("document_review")
    source = task["source"]
    suffix = PurePosixPath(source["path"]).suffix.lower()
    if (not isinstance(recorded, dict) or type(recorded.get("text_budget")) is not int
            or not 1 <= recorded["text_budget"] <= MAX_REVIEW_BYTES):
        raise ContractError("DOCUMENT_REVIEW_REQUIRED", "Prepare bounded document materials before checking or publishing")
    page_budget = recorded.get("page_budget")
    if page_budget is not None and (type(page_budget) is not int or not 1 <= page_budget <= 1000):
        raise ContractError("DOCUMENT_REVIEW_REQUIRED", "Invalid recorded page constraint")
    scope, index, packet, entries = material(source, loaded, recorded["text_budget"], page_budget)
    pdf_scope = _pdf_scope(scope, entries)
    if (recorded != scope or task.get("pdf_review") != pdf_scope
            or document_parser.safe_path(root, PACKET, [".build/materials"]).read_bytes() != packet
            or document_parser.safe_path(root, INDEX, [".build/materials"]).read_bytes() != canonical_bytes(index)):
        raise ContractError("DOCUMENT_REVIEW_MATERIAL_CHANGED", "P1 reading material has changed")

    if "source_units" in plan:
        ranges = _plan_ranges(plan["source_units"], scope["total_units"])
        if len(ranges) != 1 or plan["source_units"] != ranges:
            raise ContractError("DOCUMENT_REVIEW_SCOPE", "Use one continuous source_units range")
        [[first, last]] = ranges
    elif "source_pages" in plan and suffix == ".pdf":
        pages = plan["source_pages"]
        normalized = _plan_ranges(pages)
        if len(normalized) != 1 or pages != normalized:
            raise ContractError("DOCUMENT_REVIEW_SCOPE", "Use one continuous source_pages range")
        [[page_first, page_last]] = pages
        selected = [i for i, entry in enumerate(entries, 1) if page_first <= entry["page"] <= page_last]
        if not selected or entries[selected[0] - 1]["page"] != page_first or entries[selected[-1] - 1]["page"] != page_last:
            raise ContractError("DOCUMENT_REVIEW_SCOPE", "Selected pages are outside the original PDF")
        first, last = selected[0], selected[-1]
    elif suffix != ".pdf" and scope["start_unit"] == 1 and scope["end_unit"] == scope["total_units"]:
        # Whole-document Office plans from older skills are unambiguous.
        first, last = 1, scope["end_unit"]
    elif pdf_scope is not None:
        raise ContractError("PDF_REVIEW_SCOPE_REQUIRED", "Declare actual source_units or source_pages in the PDF plan")
    else:
        raise ContractError("DOCUMENT_REVIEW_REQUIRED", "Declare actual source_units in the plan")
    if first != scope["start_unit"] or not first <= last <= scope["end_unit"]:
        raise ContractError("DOCUMENT_REVIEW_SCOPE", "Select within the prepared range from the first unreviewed unit")
    reviewed = normalize_page_ranges([*scope["reviewed_units"], [first, last]], len(entries))
    return {"review_sha256": scope["review_sha256"], "reviewed_units": reviewed,
            "source_units": [[first, last]], "total_units": len(entries),
            "remaining_units": remaining_page_ranges(len(entries), reviewed),
            "pdf_batch": {"pages": [[first, last]], "total_pages": len(entries)} if pdf_scope is not None else None}


def _plan_ranges(ranges, total=None):
    try:
        return normalize_page_ranges(ranges, total)
    except ContractError as error:
        raise ContractError("DOCUMENT_REVIEW_SCOPE", "Use valid start and end positions from the prepared document") from error
