---
name: hs-knowledge-publish-handoff
description: Prepare a publishing handoff from an authenticated committed local knowledge transaction, leaving Git and CI actions to authorized external actors.
---

首次使用或缺项目入口信息时，先用已安装的 `hs-knowledge-explore` 运行 setup 并读取项目 `config.yml`；已具备上下文就直接复用。默认使用实际执行机器已有的全局 Python，缺依赖时再由 setup 补齐。

跨机器连接信息放在该 Skill 的 `config.env`，由 Agent/harness 按提示通过 SSH 到服务器执行并检查结果，不要求复制工具或另建 runner。请求、稿件和结果继续放实际知识根已有的 `.build/`、`logs/`、`artifacts/`。

本 Skill 可由人工单独调用。只校验本次业务输入、实际文件及输出，不检查 Workflow 顺序或上游通过凭证。流程顺序、角色分工与交棒合法性由 OpenFlow 的 Workflow 管理；人工测试时由人选择顺序。

Input requires `operation_id` and `view_ref`; an optional `apply_result_ref` may supply that view. The Skill checks actual final file bytes and deletions to prepare the exact `commit_files` list. It does not require upstream apply/query-regression passing credentials.

This optional helper is outside local ingest completion. Readiness describes the local bytes selected for submission, not workflow approval or a Git commit.

A person submits the applicable changes, triggers the fixed CI and merges afterward. If they use this helper, they commit only `commit_files` and may call `--action verify-submission` with the exact `commit_sha`. The node rechecks readiness and actual HEAD Git blobs, deletions and changed-file scope, and returns `submitted` only for that real scoped commit. These publishing results do not change whether local ingest has completed. The tool never performs Git writes, push or merge, installs CI policy or claims remote acceptance. The fixed CI reuses the lint checks on submitted data; it is not an additional Agent workflow or semantic review. Synthetic proof retains its synthetic tier; independent review does not prove real-host isolation.


Use the execution host global Python with `scripts/cli.py --input REQUEST.json --output RESPONSE.json --knowledge-root K`; choose a documented `--action` when needed. Resolve paths from the actual project and installed Skill, never from source prose. `--rules-digest` is optional; omission uses the current framework lock and still verifies its files. Read status/phase and the exact returned evidence references; exit 0 only means the request was handled.
