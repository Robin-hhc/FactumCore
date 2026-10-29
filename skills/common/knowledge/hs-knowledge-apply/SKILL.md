---
name: hs-knowledge-apply
description: Safely execute a local knowledge batch and its indexing, declared queries and activation; also build indexes, check regressions and describe scoped submissions independently.
---

首次使用或缺项目入口信息时，先用已安装的 `hs-knowledge-explore` 运行 setup 并读取项目 `config.yml`；已具备上下文就直接复用。默认使用实际执行机器已有的全局 Python，缺依赖时再由 setup 补齐。

跨机器连接信息放在该 Skill 的 `config.env`，由 Agent/harness 按提示通过 SSH 到服务器执行并检查结果，不要求复制工具或另建 runner。请求、稿件和结果继续放实际知识根已有的 `.build/`、`logs/`、`artifacts/`。

本 Skill 可由人工单独调用。只校验本次业务输入、实际文件及输出，不检查 Workflow 顺序或上游通过凭证。流程顺序、角色分工与交棒合法性由 OpenFlow 的 Workflow 管理；人工测试时由人选择顺序。

`batch` requires `operation_id` and the exact P4 `view_ref`; an authored v3 batch also supplies its pending P6 `ingest_record_ref` so content and processing facts land together. This is business data, not a credential that a prior node passed. The compatibility `run` action also accepts a record-only `ingest_record_ref` without a content view. Review and lint results are optional supporting data; any supplied records must retain their exact business bindings.

The seven-stage ingest uses `--action batch`. It checks the actual input snapshot, allowed targets, exact old/new bytes and recoverability, then applies the content and processing record together. It builds and fully verifies the actual candidate index, checks the author's frozen query cases and same-generation reads, and activates with the original expected-active baseline. These steps run in one process. Knowledge quality and independent content/code review belong to P5 lint; the new batch does not rerun full-library quality checks and does not require a passing lint receipt, Workflow identity or reviewer chain. Its transaction tier is `transaction_bytes_only`, not semantic acceptance.

The existing default `run` remains a compatibility action and retains its full fixed business checks. Request JSON cannot change that action to safety-only execution. It never infers independent review or writes a supported acceptance summary merely because bytes were applied. OpenFlow decides when review, lint and other workflow nodes must have run.

Writes retain the cooperative writer lock, full-write-set CAS, durable backups and recovery journal. Originals stay read-only. A conflict leaves external edits untouched. `committed` means local transaction completion; Git submission and merge remain human actions.

Use `--action batch|index-build|index-verify|index-activate|regression|regression-verify|prepare-submission|verify-submission` for the new public uses; see [actions and recovery](references/execution.md). Independent index and regression actions accept actual formal assets, generation and explicit cases without a producer view or private processing history. Query behavior is shared through public domain functions, never another Skill CLI.

Keep `--action run|inspect|resume|rollback|verify-result` for existing transaction uses. Inspect unclear interrupted state before recovery. A committed transaction is changed through a new operation. `verify-result` checks recorded transaction bytes and exact current or retained historical content; it does not grant workflow eligibility or certify reviewer identity. Fault injection stays restricted to isolated synthetic fixtures.

Use the execution host global Python with `scripts/cli.py --input REQUEST.json --output RESPONSE.json --knowledge-root K`. `--rules-digest` optionally fixes the actual framework lock; omission still verifies the locked business rules. Read status/phase, diagnostics and returned references. See [artifact contract](artifacts/result.yaml).

P7按冻结stage→final映射发布已审原字节及必要证据，内容落位并核验后发布正式成功record；适用索引、冻结查询和激活完成后才清本批可删owned暂存。正式结果在 `logs/publications/<op>/`，必要证据在 `logs/evidence/published/`。published/content_applied成功与cleanup_pending分开，清理失败不回滚已发布知识，batch_complete仍为false；重入只补缺失收尾／清理。借用、保护及用途不明项保留并说明，小型最终CLI响应仍可在.build。新事务与backups在本批transaction子目录，稳定writer锁不随批清理。正式结果读取、verify-result和提交核对不要求已清的旧view；旧事务仅按明确原ref与配套版本恢复，不自动迁移。
