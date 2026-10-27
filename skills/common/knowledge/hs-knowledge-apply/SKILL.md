---
name: hs-knowledge-apply
description: Apply an exact reviewed knowledge view using complete-write-set CAS, a cooperative writer lock, durable backups and one recovery journal.
---

首次使用或缺项目入口信息时，先用已安装的 `hs-knowledge-explore` 运行 setup 并读取项目 `config.yml`；已具备上下文就直接复用。默认使用实际执行机器已有的全局 Python，缺依赖时再由 setup 补齐。

跨机器连接信息放在该 Skill 的 `config.env`，由 Agent/harness 按提示通过 SSH 到服务器执行并检查结果，不要求复制工具或另建 runner。请求、稿件和结果继续放实际知识根已有的 `.build/`、`logs/`、`artifacts/`。

本 Skill 可由人工单独调用。只校验本次业务输入、实际文件及输出，不检查 Workflow 顺序或上游通过凭证。流程顺序、角色分工与交棒合法性由 OpenFlow 的 Workflow 管理；人工测试时由人选择顺序。

Input requires `operation_id` and `view_ref`. A `record_only` batch can instead supply `ingest_record_ref`; it cannot write knowledge content. Review results, lint reports and processing records are optional supporting data, not prerequisites proving earlier Workflow steps passed. When supplied, their exact record/view bindings must remain consistent.

Apply validates final card structure, source references and recoverability, and reruns full fixed business checks against the actual proposed view. It does not ask for passing review/lint credentials or follow a plan-author approval chain. It never infers independent review or writes a supported acceptance summary merely because bytes were applied. OpenFlow decides when review, lint and other workflow nodes must have run.

Writes retain the cooperative writer lock, full-write-set CAS, durable backups and recovery journal. Originals stay read-only. A conflict leaves external edits untouched. `committed` means local transaction completion; Git submission and merge remain human actions.

Use `--action run|inspect|resume|rollback|verify-result`. Inspect unclear interrupted state before recovery. A committed transaction is changed through a new operation. `verify-result` checks recorded transaction bytes and exact current or retained historical content; it does not grant workflow eligibility or certify reviewer identity. Fault injection stays restricted to isolated synthetic fixtures.

Use the execution host global Python with `scripts/cli.py --input REQUEST.json --output RESPONSE.json --knowledge-root K`. `--rules-digest` optionally fixes the actual framework lock; omission still verifies the locked business rules. Read status/phase, diagnostics and returned references. See [artifact contract](artifacts/result.yaml).
