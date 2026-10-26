# Mechanism acceptance

Current admission uses independent Agent content review for documents and additional local-check evidence for code/mixed views. No human gate, signed host event or adapter is required. Tests cover document admission without a human adapter, author conflict, exact-view invalidation, obsolete approval/proof-set rejection, complete write-set CAS, cooperative locking, idempotence and interrupted resume/rollback. Altered journals and external edits remain blocked before destructive recovery.

Public CLI tests exercise copied versioned contracts, document review/apply/eligibility, workflow result binding, retained source recovery, old-rules journal liveness and unpinned bytecode rejection. Fixtures use synthetic content and declared independent reviews; they do not establish real semantic quality, remote CI or access-control acceptance. The unit Context injection seam is never used by the installed CLI. Per-package totals are reported by the current runner.

Non-v3 regression cases reject a mixed batch with only code proof, changed content-review records during recovery, a document review missing its exact change-plan binding, invalid full-view navigation and unrecoverable exact sources before the first write. Public fixtures use actual change-plan records and complete navigation; they do not fabricate an additional semantic plan.
