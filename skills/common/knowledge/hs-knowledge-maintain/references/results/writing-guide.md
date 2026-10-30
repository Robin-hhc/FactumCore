# Writing guide

Report the actual CLI status, phase, diagnostics and returned business file references. Use the output of this invocation; do not invent a passing result. OpenFlow owns run/node/attempt tracking and transition checks.

Separate independent explicit event/watermark writes from read-only reports and ingest pending event drafts. Do not describe this action as regular stage cleanup.

For patrol, include the exact plan_ref/report_ref, counts, coverage, fallback reasons and unresolved items. Hand source_request verbatim to source.prepare. Separate observed changes from actual P7 completion and the successful baseline CAS; pending is not completed. Use exact resume_request for an unfinished publication, never invent an old producer or replay its writes.
