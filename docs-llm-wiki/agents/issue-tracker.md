# 本地任务跟踪

使用 `docs-llm-wiki/sdd/knowledge-v1/tasks.md` 及其 `tickets/Txx.md` 作为本项目本地 tracker。不因布局迁移自动创建远端 issue；编号和依赖由 traceability.json 校验。

状态：planned、ready、in_progress、implemented、verified、external_validation_required、deferred。只有验收证据存在才写 verified。未满足依赖的任务不执行；架构已经用户批准，本轮按既定范围自主拆分与执行，无需重新审批普通任务颗粒度。

没有安装 triage 流程，不另建远端标签或标签文件。开发与域内知识的记录分别管理，SDD 不自动摄入为知识卡。
