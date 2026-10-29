# Writing guide

Report the actual CLI status, phase, diagnostics and returned business file references. Use the output of this invocation; do not invent a passing result. OpenFlow owns run/node/attempt tracking and transition checks.

Report formal publication/completion references, actual published/content_applied and batch_complete separately, plus cleanup status/deleted/retained/failed. Cleanup pending preserves published facts and requires only missing tail/cleanup retry; Git/CI remain separate.
