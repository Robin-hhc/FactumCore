# Candidate-generation regression 2.0

Use the public `scripts/cli.py` with the actual `--knowledge-root`. Rules default to the current framework lock; no catalog or upstream apply result is required. Request:

```json
{"operation_id":"check-generation","generation_ref":"artifacts/indexes/local/gen-<id>/manifest.json","expected_active":null,"cases":[{"id":"rule-can-be-found","query":"capture","purpose":"current","context":{},"required":["rule-id"],"forbidden":["wrong-id"]}]}
```

`expected_active` is the exact current active-pointer digest returned by index-build, or null for the first generation. Every case needs a unique nonempty ID/query and an explicit oracle: nonempty `required`, nonempty `forbidden`, or `expected_order` (including an explicitly empty result list). Oracle values are unique card IDs. Optional `top_k` defaults to 5; purpose/context use the query contract. A case with no expected behavior is invalid and cannot activate an empty or untested generation.

The node verifies a fixed immutable generation, evaluates each query through query's public evaluation mode, records actual receipts, and requires no candidate-scan truncation. Any failed assertion returns `phase: needs_revision`, `passed:false`, `activated:false`. All passing assertions permit index-build's public CAS activation; a concurrent baseline, validity or active-pointer change blocks activation. A passing synthetic regression proves the tested retrieval behavior, not semantic correctness or CI publication.

Optional `view_ref`, or `apply_result_ref` used to locate that view, supplies bound business data. If `cases` is omitted, the node uses the view's `target_queries`; explicitly supplied nonempty cases take precedence for independent use. OpenFlow must pass the original P3 case set for the ingest batch. These optional references do not establish upstream passing credentials, and `v3_required` is not a separate execution gate.

`--action verify` takes `report_ref` and reruns its fixed generation and cases. Success returns `gate_verified:true` without activation; it does not grant workflow eligibility, certify semantic review or require Git submission. Keep the actual generation, report and activation result distinct when reporting progress.
