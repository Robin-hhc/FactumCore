# Search and same-generation read

Use this package's public `scripts/cli.py` with input/output and the actual K.
Rules default to the actual framework lock; no catalog is required. Actions are `search`, `read`, `receipt`.

A formal `search` chooses the actual active generation. Its immutable
`search_receipt` stores effective `request_binding` (action, query, budgets,
channel, generation, purpose and Target context), request/result digests, the
generation-manifest digest and the active-pointer observation read at search
time. Matches include exact `card_digest` and the eligible `claim_ids`. Only
these query fields are retained; arbitrary extra request fields and credentials
are not copied into the binding. Context contains query scope, never credentials.

To read a search hit after active changes, call `read` with a new `operation_id`,
the original `receipt_ref`, and `card_id`. Missing channel/purpose/context and
generation are inherited from the original search. Explicit differences are
rejected. Optional `claim_ids` must be a nonempty subset of the original hit;
reads never add claims that were absent from that search. Exact card bytes and
the original generation manifest must still match. Legacy receipts without
these bindings require a fresh search.

The original record must be a successful, non-evaluation `search` receipt, not a
read receipt or an evaluation result. A candidate `generation_ref` remains
evaluation-only when supplied directly. A formal receipt read stays formal and
retains the original generation even after a new generation activates.

Receipt hashes and active-pointer observations provide integrity and lineage
under the existing local artifact trust model. They are not origin signatures,
ACLs or independent content/code review. They retain data integrity, source and dependency checks. Skill calls do not
require upstream passed reports or a Workflow qualification chain. Current reads check actual
source/configuration bytes; historical reads keep the exact retained source. If no
original record or eligible claim remains, the read is refused.

If a public source-resolution call times out, search, receipt and read return
`status: blocked` with the original backend timeout diagnostic and no answer
data. The same applies while qualifying dependencies or rechecking a result
before output. A timeout is not a stale-source finding or a valid zero-hit
answer. Normal source absence and non-current source qualification retain
their existing per-Claim filtering and gap reports. This handling adds no
Workflow identity, predecessor or handoff checks.

Without `receipt_ref`, `read` keeps the existing behavior of using the current
active generation. A `read` receipt links back to its source search for audit;
use the original search receipt for subsequent reads.

Shared repository snapshots bind an explicit Git commit and card hashes. The consumer verifies actual Git blobs, current record
bytes, rules, source references and Claim scope; another machine's private
operation log or `.build` directory is not required. A digest alone or an
uncommitted local record does not establish a repository snapshot. Code/current use also
requires the current configuration fingerprint and actual referenced code
bytes to match; unknown or changed context restricts those Claims.

A source declaring `code_ref` also returns `code_navigation` from the common source resolver. Active-card code sources require the field at fixed lint/CI; historical recovery and deprecated cards remain compatible with four-field references. Its status is resolved, missing, ambiguous or unavailable; only a unique resolved result supplies a current range. The original source_ref, snapshot and locator remain fixed evidence. Current positions never rewrite that locator, and current_source_matches still reports whole-file byte equality. Navigation is rechecked during the query; changed navigation identity/status is not silently substituted between qualification and output. Guidance source-file drift does not by itself negate the document's background conclusion; current/implementation qualification keeps its existing source/configuration/build checks. A symbol result does not prove semantics or which conditional definition is active.

The same code_ref is stored in card metadata and compiled Claim.source_records, so no new query index table, card-level symbol registry or CodeGraph node ID is needed. Rebuild derived indexes after adopting new locked rules; do not modify old generations. CodeGraph may assist the Agent with candidates and call relationships, but public fixed checks do not call MCP or install/build a graph.

P2 maintenance candidate discovery is exposed by `hs-knowledge-source-prepare` and
the shared knowledge relation functions. It includes non-answer states and
does not relax this query API's answer eligibility. New-search index freshness
checking is outside this change; generation integrity and same-generation
read checks remain mandatory.
