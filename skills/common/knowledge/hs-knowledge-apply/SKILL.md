---
name: hs-knowledge-apply
description: 将已确定的知识批次及处理记录安全落位，完成索引、冻结查询、激活和本批收尾；也处理明确指定的索引或事务维护任务。
---

# 发布与检索收尾

## 目标与输入

P6 发布本批已经确定的字节和处理事实，完成适用检索收尾。接收本次 `view_ref` 和 P5 的 `ingest_record_ref`；不重判内容、不重新生成稿件或重复 P4 质量审阅。

复用已知知识根和执行端；缺位置时读当前工作区 `AGENTS.md`、`config.yml`，必要时询问用户。首次读知识根 `AGENTS.md`；以下在该目录执行，POSIX 用 `sh ./knowledge.sh`。

## 正常入库

```powershell
.\knowledge.cmd apply --action batch --input REQUEST.json --json
```

REQUEST.json 传 `operation_id`、本批实际 `view_ref` 和 `ingest_record_ref`。CLI 在一次调用中执行：

1. 核对输入与旧基线，安全落位冻结内容、必要证据和处理记录。
2. 为内容批构建并完整验证真实索引，执行 P2 原冻结查询及同代精读，按原活动指针基线激活。
3. 保存正式发布／完成记录，清理本批明确可删的暂存；借用或受保护材料保留并说明。

沿用真实返回引用与原查询预期，不手工拼装摘要、放宽断言或替换激活基线。仅记录批保留处置及欠账，不建索引。

## 判断完成

- `batch_complete: true` 才表示本批适用落位、检索收尾和清理完成；记录批按其实际结果交付。
- `published`／`content_applied` 与 `batch_complete` 分别报告。已发布但 `cleanup_pending` 时保留发布事实，按同一操作重试缺失收尾或清理。
- 查询失败、输入冲突或运行故障时保留实际停点和诊断；不要重复发布已落位内容、另选激活基线或回滚已经成功发布的批次。

交付实际 `publication_ref`、`completion_ref`、索引／查询结果及剩余事项。`committed` 仅表示本地事务状态，Git 提交、CI 和合入另行处理。

## 按需维护

- 中断事务、旧事务或发布后重试：[执行与恢复](references/execution.md#中断与恢复)。先按确切操作观察，再选择恢复；旧历史不迁移、不改签。
- 明确要求独立建库、校验或激活：[索引维护](references/shared-publication.md#独立索引动作)。
- 明确要求独立查询回归：[回归请求](references/regression.md)。正常 batch 已包含原冻结用例，不再另跑一套。
- 准备或核对人工 Git 提交范围：[提交核对](references/execution.md#提交核对)。这些动作本身不提交或推送。

写锁、完整写集 CAS、备份和落盘核验由 CLI 执行。保留冲突处的外部修改；原件、正式证据、其他操作和运行环境不属于本批清理目标。
