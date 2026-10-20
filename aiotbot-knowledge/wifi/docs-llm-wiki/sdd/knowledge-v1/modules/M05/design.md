# M05 人工确认与事务：开发设计

## 接口与依赖

| 模块 | 文件 | 对外接口 | 依赖与边界 |
|---|---|---|---|
| M05 人工确认与事务 | `S/changes.py` 公共确认包装；`S/confirmations.py` 人工适配；`S/transactions.py` 事务 helper；人工模板及持久日志 | 当前 `confirm_document(knowledge_root, operation_id, ...)`、`validate_review(...)`、`narrow_document(...)`；CLI apply 调用 `transactions.apply_document(knowledge_root, operation_id, review_ref)`；原设计的完整 recover 接口留 T08 | 依赖 M04；代码证明由 M06 提供。确认绑定最终字节/来源/scope；锁+CAS+全域 ID/关系技术视图；只改明确清单，保留其他工作。T07 不能代替 T08 恢复验收 |

## 当前实现分工与持久路径决议

`changes.py` 负责计划、物化、确切视图核验与通用安全写入，并保留 confirm/validate_review/narrow 的公共包装；`confirmations.py` 执行交互终端挑战、记录绑定校验和严格子集新视图编排；`transactions.py` 提供领域协作写锁和 apply_document，执行确认/基线核验、全域技术视图、备份、write-ahead journal、按清单替换、结果重放及当前异常处理。CLI 只连接这些实现，不复制另一套确认或事务规则。

T07 将唯一 journal、备份与结果放入 `K/logs/operations/<operation_id>/`，避免清理候选暂存 `.build/` 时丢失恢复材料。下表原路径继续追踪批准设计；当前运行程序以 implementation_path 为准，不同时生成两套 journal。它是内部存储落点的落实决策，不改变确认→本地 stable 的业务流程，也不表示完整 recover 已完成。

| 原设计路径（相对 K） | 当前 implementation_path（相对 K） |
|---|---|
| `.build/<operation_id>/transaction/journal.json` | `logs/operations/<operation_id>/journal.json` |
| `.build/<operation_id>/transaction/backup-manifest.json` | `logs/operations/<operation_id>/backup-manifest.json` |
| `.build/<operation_id>/transaction/backups/<file-key>.bin` | `logs/operations/<operation_id>/backups/<target-path-sha>.bin` |
| `logs/operations/<operation_id>.json` | `logs/operations/<operation_id>/result.json` |

`<target-path-sha>` 是目标相对路径 UTF-8 字节的 SHA-256；备份仍保存旧文件原字节，新建目标通过清单记录原文件不存在。相关持久日志不能按可重建缓存清理。当前 apply 发现未完事务会报告 RECOVERY_REQUIRED 并阻止新写入；跨进程中断后的完整续做/恢复仍归 T08。T07 的实际验收以随后生成的 `records/T07-verification.md` 为准，不用此设计映射替代通过记录。

## 本模块拥有的文件与生成规则

| 路径 | 类别 | 开发动作 | 验收要求 |
|---|---|---|---|
| `skills/common/knowledge/_shared/changes.py` | F | 保留原设计职责追踪；当前 plan/materialize/最终视图与安全写入在此，人工适配委托 confirmations.py，写锁/CAS/journal/幂等 apply 委托 transactions.py；完整 recover 留 T08 | 修改候选后旧证明失效；部分接受须重做最终确认；各票按实际范围验收，非本任务脏文件保留 |
| `skills/common/knowledge/_shared/tests/test_changes_checks.py` | F | 六决策逐一构造 final-view；篡改摘要、过期基线、人工拒绝/部分接受、H/B/T/V 变化和写入故障注入 | 同字节通过、改字节失效；两门禁不写输入；人工无回复不应用；各故障点可回滚/续做 |
| `aiot-wifi-knowledge/governance/templates/manual-review.json` | F | 复用 records Schema，留真实决定、确认主体与证据位 | 无明确人工决定保持待确认，不能 apply |
| `aiot-wifi-knowledge/.build/<operation_id>/review-package.md` | R | 展示原件/附件差异、逐 Claim 新旧结论、定位、范围、缺口及目标摘要 | 部分接受后重新生成 final-view 并取得真实确认 |
| `aiot-wifi-knowledge/.build/<operation_id>/transaction/journal.json` | R | 顺序记录 prepared/replacing/committed/恢复状态及每文件摘要 | 任一步中断均可完成或受控恢复，未提交部分不被新索引消费 |
| `aiot-wifi-knowledge/.build/<operation_id>/transaction/backup-manifest.json` | R | 记录目标路径、原摘要、备份路径与新摘要 | 回滚只恢复仍匹配本次已写摘要的目标 |
| `aiot-wifi-knowledge/.build/<operation_id>/transaction/backups/<file-key>.bin` | R | 修改前保存并核对摘要 | 恢复后字节与原摘要一致；他人后续修改保留 |
| `aiot-wifi-knowledge/logs/operations/<operation_id>.json` | R | 记录 ChangeSet、基线、执行状态、确认/核验和提交关联 | 清理 .build 后仍可定位本次确认和变更范围 |
| `aiot-wifi-knowledge/logs/document-reviews/<review_id>.json` | R | document confirm 记录真实人的决定、最终目标、来源和限制 | 没有真实动作无法伪造 accepted；改字节后 REVIEW_STALE |

上表的 transaction/operations 四项保留 design_path；当前运行路径按前述映射，不另建旧位置副本。完整职责与约束字段见 ../../traceability.json，同一路径只有一个主模块。F 为固定实现，D/R/X 是实例、产物或外部入口，P 首发延期；不得手造不存在的业务工程或成功证据。
