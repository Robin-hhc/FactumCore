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

## Card content and source addresses

`search` keeps card IDs, eligible `claim_ids`, allowed titles/summaries, logical
card `path`, score and exact `card_digest`, and adds `card_ref` for the exact
card file retained in the selected generation. `read` returns the eligible
Claim text with both card addresses. `path` and `card_ref` are relative to the
actual knowledge root K. A logical path may now hold a newer formal card; use
the original receipt's read result and `card_ref` for the same-generation bytes.
Opening a card file does not enlarge the original eligible Claim set.

Both actions return `source_links` instead of expanded `sources`. Each link has
`evidence_ref` and `kind`, an `evidence` address for the fixed original, and a
separate `current` address when available. An address uses `base`, `path` and
an applicable `locator`; a Git address also retains the necessary `commit` and
`repo_id`. Evidence may include its exact original `sha256` without expanding
the snapshot object. Address bases are explicit:

| `base` | Interpret `path` from |
|---|---|
| `knowledge_root` | The actual knowledge root K; raw/current paths and retained local evidence objects use this base. |
| `workspace` | The project root selected by the actual `config.yml`; module paths may be nested under its `code_root`. |
| `repository` | The authorized repository/scope identified by `repo_id`; do not join it to K. |
| `git` | The exact local `commit` and repository-relative `path`; code evidence supplies `repo_id`, while its omission selects the workspace Git repository for raw evidence. |
| `absolute` | A currently readable dbox file's native absolute path on the actual execution host. It may also address the exact registered original when retained evidence is missing and the observed bytes match the frozen snapshot. Do not join it to K or reinterpret a server path on the caller's machine. |

Do not assume K's parent is the project or repo root. A configured
`code:<repo_id>:<path>` recovery reference is exposed as its resolved workspace
or repository address, not as a path to append to K.

Configured dbox files keep their fixed evidence in the published objects under
K. Their `current` address, when available, uses `absolute`; its hash and optional
locator come from the same actual observation. A changed document has no current
locator borrowed from its old version. Without a readable local mapping,
`current` and `current_source_matches` are null while exact retained evidence may
remain readable. Historical/guidance queries retain their existing qualification
rules; current/implementation queries still require actual current evidence.
If the retained original is unavailable, recovery may use only the unique
registered dbox location whose actual bytes match the frozen hash and size. In
that case `evidence` also uses `absolute`, with the same checked path and hash;
an arbitrary absolute file is not an accepted recovery location. These addresses
may appear in this response and its private query receipt, never in formal source
identities or publication assets.

A query compares its dbox directory binding between initial qualification,
fresh qualification and the final source check. Switching to another root with
identical bytes during that call requires retry. A later search or receipt-bound
read observes that call's actual local mapping; the producer's or a previous
query's private directory binding is not a permanent consumption prerequisite.

Code links retain `navigation_status` and `current_source_matches`. Navigation
is `resolved`, `missing`, `ambiguous` or `unavailable` when a symbol is declared;
raw and legacy no-symbol references use `not_applicable`. Only a resolved
current symbol supplies its current range. A legacy no-symbol code reference
may reuse its old locator only when the current bytes match exactly. The
evidence locator still describes the fixed old source; changed raw text does
not inherit its old line numbers. For declared-symbol code, the `current`
path, locator and `sha256` come from the same actual `code_navigation` file
observation, including any path selected by a legacy locator. `missing` or
`unavailable` without an actual file digest returns `current: null`; an
`ambiguous` result with a file digest may return the file address with
`locator: null`. The external `current_source_matches` compares this current
file digest with the fixed evidence digest, and is null when `current` is null.
This projection does not change the internal resource-based qualification
checks. Current position, whole-file byte equality and semantic applicability
are different observations.

Locators keep the original source format: lines for readable code/MD/TXT,
pages for PDF, and paragraphs/table rows for DOCX. A retained evidence object
may require the existing exact-source recovery capability to interpret it;
native page or paragraph locators are not line numbers in an extracted TXT.
Evidence addresses identify the actual original object, rather than silently
substituting extracted text for that original.

The response and newly sealed `receipt.result` contain card content and these
addresses. They omit recovered source text, original bytes/Base64 and complete
`source_ref`, `snapshot`, `resource` or `code_ref` objects. The Agent opens the
returned locations only when the question needs source detail. A link is not a
claim that its target has been read by the Agent. If exact recovery metadata is
needed, read the card's governed source binding and use the existing explicit
source-recovery capability; query does not introduce another lookup action.

Source recovery, hash/size checks, symbol checks, qualification and the final
current-state recheck still run internally before output. P2's independent
source-resolution result retains its existing contract.

## Same-generation receipt reads

To read a search hit after active changes, call `read` with a new `operation_id`,
the original `receipt_ref`, and `card_id`. Missing channel/purpose/context and
generation are inherited from the original search. Explicit differences are
rejected. Optional `claim_ids` must be a nonempty subset of the original hit;
reads never add claims that were absent from that search. Exact card bytes and
the original generation manifest must still match. Legacy receipts without
these bindings require a fresh search.

Existing bound receipts with expanded source results remain readable after
their original record/result digests and current rules binding pass validation.
This preserves the old result shape, not an exemption from `STALE_RULES`; a rules
upgrade does not authorize stale receipts. Old records are not edited or
re-signed. A new read emits the compact result and seals its new receipt from
that actual result.

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

A source declaring `code_ref` is checked through the common resolver's internal `code_navigation`. Active-card code sources require the field at fixed lint/CI; historical recovery and deprecated cards remain compatible with four-field references. The external `source_links` projects the actual status and addresses from that checked result. Navigation is rechecked during the query; changed identity/status is not silently substituted between qualification and output. Guidance source-file drift does not by itself negate the document's background conclusion; current/implementation qualification keeps its existing source/configuration/build checks. A symbol result does not prove semantics or which conditional definition is active.

The same code_ref is stored in card metadata and compiled Claim.source_records, so no new query index table, card-level symbol registry or CodeGraph node ID is needed. Rebuild derived indexes after adopting new locked rules; do not modify old generations. CodeGraph may assist the Agent with candidates and call relationships, but public fixed checks do not call MCP or install/build a graph.

P2 maintenance candidate discovery is exposed by `hs-knowledge-source` and
the shared knowledge relation functions. It includes non-answer states and
does not relax this query API's answer eligibility. New-search index freshness
checking is outside this change; generation integrity and same-generation
read checks remain mandatory.

After P7 cleanup, normal reads use the published source/material closure and the selected real generation. Soft producer stage/view references do not require reopening those paths. Explicit receipt reads retain their exact generation dependencies; missing retained generations require a fresh query rather than history guessing.
