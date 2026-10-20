# Requests

`register-source-change`: operation_id, bundle_ref. Changes are derived from the actual current source lock and fixed bundle, not accepted from caller assertions. `status`: operation_id. `advance`: operation_id, apply_result_ref, generation_ref. Raw originals are read-only; unresolved human, code, activation or source evidence keeps blocks intact.

`recover-events`: operation_id. Completes only the exact sealed source events retained in pending state, including fixed resource/snapshot and affected Claim identities; does not clear a block or need temporary capture files. Pending blocks/epoch are durable before the event publish, and scan watermark advances only after event persistence. Repeated source versions carry explicit observed-snapshot event identities.
