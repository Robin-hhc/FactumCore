# New operation after returned or partial review

Request: a NEW `operation_id`, `previous_view_ref`, `revision_reason`, and newly authored `decisions`; optional `candidate_ids` and `context_ref`. Reusing the previous operation is rejected. The node resolves old source identities, captures current explicit local raw bytes, and invokes public planning/materialization for a new fixed view.

Result includes `view_ref`, `revision_ref`, and `content_review_required:true`. Old content-review, check and apply proofs do not authorize the revision. All-deferred revisions retain their plan/dispositions and terminate deferred. No official changes occur.
