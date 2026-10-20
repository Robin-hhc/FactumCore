# Capture and exact-source resolution

Capture request: `operation_id`, `source_path`, `source_id`; optional `version`, explicit `attachments`, `context_ref`. Only landed `docs-raw/{conventions,chips,storys,specs,protocols}` files are supported. Primary MD/TXT must be nonempty UTF-8, PDF needs a text layer on every page, DOCX supports paragraphs/tables with explicit visual gaps. No URLs, sources links, OCR, active content, network access or writes to originals.

`--action resolve`: `operation_id`, `bundle_ref`; verifies retained original, extraction and locator digests. `--action resolve-source`: `operation_id`, `source_ref:{evidence_ref,source_id,snapshot_id,locator}` and optional candidate `bundle_ref`. Without a bundle, resolution uses the exact formally registered snapshot, never implicit latest.

The result includes immutable original bytes, selected `text`, original locator, snapshot identity and limitations. `current_source_matches` is true/false/null after separately comparing current raw bytes. A successful historical replay does not prove current applicability. MD/TXT use `lines` start/end; PDF uses `page`; DOCX uses `paragraph` or `table_row` with table/row. Opaque attachments return no interpreted text.

Changed previously registered sources call the public `hs-knowledge-maintain --action register-source-change` before capture returns success. Missing maintenance installation blocks completion. Recovery objects remain under logs/evidence; capture never writes sources.lock, formal cards or indexes.
