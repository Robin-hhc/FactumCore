---
name: hs-knowledge-maintain
description: Register exact source-change events, block affected Claims and advance review state only from verified applied and activated evidence.
---

Use `scripts/cli.py --input REQUEST.json --output RESPONSE.json --knowledge-root K --rules-digest SHA256 --catalog CATALOG.json --action register-source-change|status|advance`. All event changes use the domain cooperative writer lock. [Request details](references/request.md) explain the proof requirements.

Source capture may register new events and blocks; it never clears them. `advance` requires public apply verification, a verified activated generation and exact current card bytes. An index rollback cannot undo live blocks. User data, URLs, model assertions and old successful test records never authorize clearing a block.

The [artifact contract](artifacts/result.yaml) requires the actual per-attempt CLI manifest.
