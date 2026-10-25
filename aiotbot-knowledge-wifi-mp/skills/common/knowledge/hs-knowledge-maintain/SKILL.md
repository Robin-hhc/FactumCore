---
name: hs-knowledge-maintain
description: Register exact source-change events, block affected Claims and advance review state only from verified applied and activated evidence.
---

Use `scripts/cli.py --input REQUEST.json --output RESPONSE.json --knowledge-root K --rules-digest SHA256 --catalog CATALOG.json --action inspect-context|register-source-change|register-code-change|recover-events|status|advance`. All event changes use the domain cooperative writer lock. [Request details](references/request.md) explain the proof requirements.

`inspect-context` 在 ingest 开始时只读比较实际来源、代码/配置和规则身份，输出受影响 Claim、依赖和缺口，不要求先登记本机变化事件。未知上下文保留限制；P2—P5 修订、P6 记录和 P7 收尾后才能解除。query 另按相同当前引用和确切资格判断过滤，不因 raw 未变而信任旧代码。

Source capture may register new events and blocks; it never clears them. `advance` requires public apply verification, a verified activated generation and exact current card bytes. An index rollback cannot undo live blocks. User data, URLs, model assertions and old successful test records never authorize clearing a block.

The [artifact contract](artifacts/result.yaml) requires the actual per-attempt CLI manifest.
