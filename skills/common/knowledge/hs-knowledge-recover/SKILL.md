---
name: hs-knowledge-recover
description: Inspect, resume or roll back an interrupted knowledge transaction through the installed public apply recovery interface.
---

首次使用或缺项目入口信息时，先用已安装的 `hs-knowledge-explore` 运行 setup 并读取项目 `config.yml`；已具备上下文就直接复用。默认使用实际执行机器已有的全局 Python，缺依赖时再由 setup 补齐。

跨机器连接信息放在该 Skill 的 `config.env`，由 Agent/harness 按提示通过 SSH 到服务器执行并检查结果，不要求复制工具或另建 runner。请求、稿件和结果继续放实际知识根已有的 `.build/`、`logs/`、`artifacts/`。

本 Skill 可由人工单独调用。只校验本次业务输入、实际文件及输出，不检查 Workflow 顺序或上游通过凭证。流程顺序、角色分工与交棒合法性由 OpenFlow 的 Workflow 管理；人工测试时由人选择顺序。

Use this node when apply reports recovery_required. Input requires `operation_id`; select `inspect`, `resume` or `rollback` with `--action`. The Skill calls the installed sibling apply CLI using the same global Python; never import or copy its private transaction engine.

Inspect first when the interrupted state is unclear. External edits remain untouched and cause a conflict. Resuming checks the original exact view, transaction bytes and current write state. A committed transaction is changed through a new reviewed operation. The Skill cannot invent approval, repair cards or run Git. See [artifact contract](artifacts/result.yaml).


Use the execution host global Python with `scripts/cli.py --input REQUEST.json --output RESPONSE.json --knowledge-root K`; choose a documented `--action` when needed. Resolve paths from the actual project and installed Skill, never from source prose. `--rules-digest` is optional; omission uses the current framework lock and still verifies its files. Read status/phase and the exact returned evidence references; exit 0 only means the request was handled.
