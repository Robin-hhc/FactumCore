---
name: hs-knowledge-apply
description: Apply an exact reviewed knowledge view using complete-write-set CAS, a cooperative writer lock, durable backups and one recovery journal.
---

Input requires `operation_id`, `view_ref`, `proof_ref`. Pure-document views require authenticated exact-view human consent; code views require a trusted local-check proof with positive Claim evidence. Apply never changes approved bytes or originals and never repairs failed checks.

The public CLI supports `run`, `inspect`, `resume`, `rollback` through `--action`. Use the recover Skill for workflow recovery. An interrupted operation requires an explicit recovery action; external edits produce a conflict and remain untouched. Committed reentry returns its prior result; a committed change is undone through a newly reviewed operation.

The OS lock coordinates cooperating writers; it does not make directories an access-control boundary. See [artifact contract](artifacts/result.yaml) for durable output. Fault injection is available only in catalog-pinned synthetic fixture roots.

