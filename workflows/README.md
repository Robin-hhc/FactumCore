# Workflow 实施入口

本目录承载公共和领域工作流。公共生产与治理的目标入口分别是 `common/hs-common-knowledge-ingest/SKILL.md` 和 `common/hs-common-knowledge-lint/SKILL.md`，职责和阶段见 [SDD 模块 M09](../docs-llm-wiki/sdd/knowledge-v1/modules/M09/design.md)。

这些编排由 T20/T21 开发并验收。本目录的存在只声明落点；尚未完成的 Skill 不视为可调用能力。编排复用 `skills/common/knowledge/_shared/`，不复制第二套执行引擎；人工确认和 stable 事务的实际状态以 SDD 开发记录为准。

本批先提供 [raw 文档手工链](../docs-llm-wiki/sdd/knowledge-v1/document-chain-usage.md)：`document capture/load-capture` → `ingest plan/materialize` → 真人 `document confirm` → `ingest apply`。部分接受经 `document narrow` 生成严格缩小的 final-view，再由真人重新确认。此处是共享 CLI 的操作说明，自动 Skill 触发、完整工作流编排和宿主部署尚待对应任务验收。

人工确认不接受名字参数、JSON 文件或 Agent 自报作为批准；当前入口由真实人控制 TTY 并输入最终视图挑战，聊天可信适配器尚未接入。apply 的职责止于本地 stable、来源锁与导航的事务落位，不隐式提交、推送、建索引或激活共享渠道。首发只接受五类 raw 已落地文件，主件提取限 UTF-8 Markdown/文本；sources 链接和 PDF/Word 主件不支持，二进制附件只保存原字节。
