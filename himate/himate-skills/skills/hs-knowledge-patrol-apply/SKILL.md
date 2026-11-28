---
name: hs-knowledge-patrol-apply
description: 发布程序校验的定位修复或已独立审阅的语义维护批次，记录实际引用结果，用于 L6。
---

# 发布关联卡维护结果

沿用本轮已确认的知识根和执行端。当前会话提供本步骤所需的 Knowledge MCP 工具时，调用该工具并沿用其绑定的知识根。采用 MCP 时，缺少工具则报告工具名，调用被拒、失败或返回 `blocked` 时按实际诊断处理。

采用 CLI 时，从知识根运行该执行端已确认的 `knowledge` 入口，每次传入同一 `--knowledge-root`。首次单独使用 CLI 时，先读取知识根的 `AGENTS.md` 和 `config.yml`，运行 `knowledge doctor --knowledge-root <知识根绝对路径> --json` 核对目标和版本。命令找不到、启动入口有明确缺项或诊断仅表明缺运行依赖时，加载 `hs-knowledge-setup`，在同一执行端补齐并复查。得到与知识根匹配的就绪回执后继续原任务。

先读取固定任务，按 `mode` 区分发布依据，再调用 `knowledge_maintain_commit`（CLI：`knowledge maintain commit --json`）。

- `mechanical`：只接收 L3 的实际 mechanical_prepared 回执与同一任务。程序会重验 `mechanical_check_ref` 指向的机械凭据、实际输入及仅定位差异；不要求 L5，也不调用 maintain check 生成内容审阅凭据。调用者的 passed 声明或片段匹配数量不能代替这份程序检查。
- `semantic` 或旧任务缺省：确认本批已由独立 L5 实际审阅通过后发布。正文无需改动时仍须交接真实确认理由，不能用机械路径绕过语义审阅。零改卡时将 `reason` 写入 `.build/commit.json`，用 `knowledge maintain commit --input .build/commit.json --json` 登记。

以命令回执交接实际 `card_ids`、`reviewed_card_ids`、引用版本/定位处理结果及 `maintenance_complete`，明确是程序定位修复还是经独立审阅的语义维护。程序只保存本批实际核验引用的 evidence_version；不手工生成或批量刷新其他引用版本。兼容回执中的 `reviewed_hash`、`source_exists` 也只按实际含义报告，不表述为整份代码已入库或所有关联卡已复核。出现 `receipt_warning` 时以本次返回值为准，不使用可能陈旧的落盘回执。

执行失败时保留固定批次和 `.build`，可恢复的执行问题修正后重试同批。确认尚未发布的语义候选必须改动时回 L4，再经 L5。机械凭据/允许差异不成立或输入需重新固定时，在确认未发布后回 L3；不手改 mode 或凭据继续发布。无法确认写入状态时保留现场并报告失败。`deferred` 保留实际缺口及待办，不宣称维护完成。成功后的后续选择由 Workflow 编排。
