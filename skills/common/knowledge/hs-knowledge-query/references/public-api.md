# Search and same-generation read

Use this package's public `scripts/cli.py` with explicit input/output, K, pinned
rules and the trusted installed catalog. Actions are `search`, `read`, `receipt`.

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
ACLs or independent content/code review. They cannot replace any application
provenance, code proof, publication verification, source or dependency check.
Current reads recheck live blockers/revocation and current exact-content proof;
historical reads use authenticated historical application content. If no
original record or eligible claim remains, the read is refused.

Without `receipt_ref`, `read` keeps the existing behavior of using the current
active generation. A `read` receipt links back to its source search for audit;
use the original search receipt for subsequent reads.

Shared repository acceptance can instead bind an exact accepted Git commit,
card hashes and `logs/ingest` acceptance summaries through a trusted signed
publication receipt. The consumer verifies actual Git blobs, current record
bytes, rules, source references and Claim scope; another machine's private
operation log or `.build` directory is not required. A digest alone or an
uncommitted local record grants no shared authority. Code/current use also
requires the accepted configuration fingerprint and actual referenced code
bytes to match; unknown or changed context restricts those Claims.

P2 maintenance candidate discovery is exposed by `source-scan prepare` and
the shared knowledge relation functions. It includes non-answer states and
does not relax this query API's answer eligibility. New-search index freshness
checking is outside this change; generation integrity and same-generation
read checks remain mandatory.
