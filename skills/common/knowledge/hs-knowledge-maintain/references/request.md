# Requests

`register-source-change`: `operation_id`, `bundle_ref`. Derives changes from the actual source lock and fixed bundle. `register-code-change` also verifies the current configured source bytes and path before recording a code change. A source ID cannot migrate to another repo/path. Repeated identical transitions are idempotent.

`status`: `operation_id`. Reports the actual recorded restrictions and unfinished source events.

`advance`: `operation_id`. Compares actual cards/Claims and exact current source references to clear resolved mechanical freshness restrictions. No apply, query, active-generation or passing-review ticket is required. Unknown or changed code/config scope remains restricted; a matching byte hash does not prove semantics or applicability. It never labels a Claim independently reviewed merely because a restriction was cleared. OpenFlow handles the content-review process.

`recover-events`: `operation_id`. Completes exact sealed source events retained in pending state. Pending restrictions and epoch remain durable before event publication; repeated source versions carry exact snapshot identities. Cooperating writer locks and before/after file checks prevent concurrent state corruption.
