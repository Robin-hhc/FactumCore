# M05 人工确认与事务：开发设计

## 接口与依赖

| 模块 | 文件 | 对外接口 | 依赖与边界 |
|---|---|---|---|
| M05 人工确认与事务 | `S/changes.py` 的 confirm/apply/recover；人工模板、journal、operations/document-reviews 日志 | `confirm_document(final_view, human_action)` 返回 `ManualReviewRecord`；`apply(changeset, proof, baseline)` 返回事务结果；`recover(operation)` 按 journal 续做/恢复 | 依赖 M04；代码证明由 M06 提供。确认绑定最终字节/来源/scope；锁+CAS+全域 ID/关系技术视图；只改明确清单，保留其他工作 |

## 本模块拥有的文件与生成规则

| 路径 | 类别 | 开发动作 | 验收要求 |
|---|---|---|---|
| `skills/common/knowledge/_shared/changes.py` | F | 实现 plan/materialize、document update-plan/confirm、最终视图摘要、写锁/CAS、journal/备份恢复和幂等 apply | 修改候选后旧证明失效；部分接受须重做最终确认；中断恢复不丢原卡、不重复应用；非本任务脏文件保留 |
| `skills/common/knowledge/_shared/tests/test_changes_checks.py` | F | 六决策逐一构造 final-view；篡改摘要、过期基线、人工拒绝/部分接受、H/B/T/V 变化和写入故障注入 | 同字节通过、改字节失效；两门禁不写输入；人工无回复不应用；各故障点可回滚/续做 |
| `aiot-wifi-knowledge/governance/templates/manual-review.json` | F | 复用 records Schema，留真实决定、确认主体与证据位 | 无明确人工决定保持待确认，不能 apply |
| `aiot-wifi-knowledge/.build/<operation_id>/review-package.md` | R | 展示原件/附件差异、逐 Claim 新旧结论、定位、范围、缺口及目标摘要 | 部分接受后重新生成 final-view 并取得真实确认 |
| `aiot-wifi-knowledge/.build/<operation_id>/transaction/journal.json` | R | 顺序记录 prepared/replacing/committed/恢复状态及每文件摘要 | 任一步中断均可完成或受控恢复，未提交部分不被新索引消费 |
| `aiot-wifi-knowledge/.build/<operation_id>/transaction/backup-manifest.json` | R | 记录目标路径、原摘要、备份路径与新摘要 | 回滚只恢复仍匹配本次已写摘要的目标 |
| `aiot-wifi-knowledge/.build/<operation_id>/transaction/backups/<file-key>.bin` | R | 修改前保存并核对摘要 | 恢复后字节与原摘要一致；他人后续修改保留 |
| `aiot-wifi-knowledge/logs/operations/<operation_id>.json` | R | 记录 ChangeSet、基线、执行状态、确认/核验和提交关联 | 清理 .build 后仍可定位本次确认和变更范围 |
| `aiot-wifi-knowledge/logs/document-reviews/<review_id>.json` | R | document confirm 记录真实人的决定、最终目标、来源和限制 | 没有真实动作无法伪造 accepted；改字节后 REVIEW_STALE |

完整职责与约束字段见 ../../traceability.json，同一路径只有一个主模块。F 为固定实现，D/R/X 是实例、产物或外部入口，P 首发延期；不得手造不存在的业务工程或成功证据。
