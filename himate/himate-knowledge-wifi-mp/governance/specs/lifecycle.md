# 知识候选、内容复核与 stable 落位

此规范说明 ingest 当前候选、独立内容复核与本地事务落位边界；实际实现与验收见 knowledge-v3。合成材料和机制测试不构成真实 WiFi 知识的语义验收。

## 状态与职责

1. plan 固定显式决策、理由、候选内容、来源捕获包和相关基线。Agent 必须提供已读来源后的明确卡正文；程序不从文本首段自动制造结论。
2. materialize 生成 `.build/operations/<operation_id>/final-view/`，其中卡已经是 stable 的确切拟写字节，同时展示同类型 index 和 sources.lock 的最终字节。正式资产此时不变。
3. 独立 Agent 读取原件、稿件及计划，复核全部最终内容并记录问题；作者修订至无未解决阻断项后，生成绑定确切计划与视图的 content_review。文档类不设真人确认门，代码类另需逐 Claim 代码依据核验。用户要求退回或缩小范围时生成新操作并重新复核。
4. P4 完整 lint 通过、P5 处理记录登记后，`hs-knowledge-apply` 在领域锁内核对独立复核、适用代码记录、当前契约／工具身份、最终视图和相关基线，成功后按明确清单同批落位。它不生成新内容，不 Git 提交或推送。

知识内容目标为与 Profile 对应的 `knowledge/**/<card>.md`、导航及 `governance/sources.lock.yaml`；P5 的本批 `logs/ingest/` 处理记录以受控附加项进入同一事务。绝对路径、父目录跳转、Windows 设备名/流名、大小写别名和链接/junction 跳转均拒绝。final-view 之外的原件、其他 dirty 文件及仓库配置不属于写入清单。

## 写前技术检查

首次 apply 重新读取已复核的 final-view 和内容／代码复核记录，固定原始字节及摘要。新文档卡必须为 stable/manual_document，退役卡为 deprecated，路径必须与七种 Profile 的规定目录一致。来源锁须结构有效，resource/snapshot ID 唯一，snapshot 所属逻辑来源可解析；卡引用固定 snapshot，Claim 引用其映射的逻辑来源。

扫描整个 knowledge 下的 Markdown 卡，叠加本次最终卡形成技术视图；不能只查 touched_paths 或忽略错误目录里的卡。每张卡须处于其 Profile 的规定目录，Card ID、Claim ID 全域唯一；relations 和 replacement 的目标卡存在，指定 Claim 属于指定目标卡；requires/replacement 图无环。index.md、AGENTS.md 为控制文件，其他非 Markdown 文件保留不动。发现无法组成有效技术视图的卡时拒绝写入并定位问题，不静默改卡。

这些是身份、引用和防覆盖检查，不认证文档语义、当前代码事实或真实 Target 覆盖，不要求 LocalCheckRecord/MergeGateRecord。进入 apply 前、prepared 之后与写入结束均复核技术视图；每次替换前再次对比目标旧摘要，结束时重新核 final-view/来源包绑定。内容、来源、scope、工具/契约或相关基线发生变化须生成新操作并重新复核、检查。

## 锁、备份与日志

领域统一竞争 `logs/operations/.writer.lock` 的 OS 排他锁：Windows 使用 msvcrt 文件字节锁，其他受支持平台使用 flock；锁冲突返回 BUSY，可稍后重试。进程退出释放 OS 锁，不能通过删除锁文件抢占写者。所有协作进程必须以同一真实 K 根工作。

每个操作的持久材料位于 `logs/operations/<operation_id>/`：

| 文件 | 内容与要求 |
|---|---|
| `backups/<target-path-sha256>.bin` | 原来存在的目标原始字节；缺失目标显式记录 absent，不造空文件冒充备份 |
| `backup-manifest.json` | 每个目标的旧摘要、最终摘要、备份引用；写后验证，摘要由 journal 绑定 |
| `journal.json` | operation、内容／代码复核引用及摘要、ChangeSet 摘要、备份清单摘要、顺序、已写目标、当前步骤和恢复诊断 |
| `result.json` | 原始成功回执；仅当 journal 为 committed 且 result 摘要相符时有效 |

先完成并核验全部备份及 prepared journal，再第一次替换正式文件。每份文件使用同目录临时文件、flush/fsync 和原子替换；每次替换前后写 journal。普通文件系统没有多文件原子提交，消费者不得因中间文件已出现就激活索引。

| journal 状态 | 含义与后续动作 |
|---|---|
| prepared / replacing | 非终态，可能已有部分新字节；任何新的领域 apply 都返回 RECOVERY_REQUIRED |
| committed | 所有明确目标及回执已核验；允许只读幂等回放 |
| rolled_back | 本次常规失败，正式目标已复核回到原摘要；其他操作可继续，本 operation 不从头盲重放 |
| recovery_required | 有外部编辑、备份/写入失败或恢复状态不能完整核验；保留现场和诊断，禁止继续写入 |

普通异常触发受控回滚：只恢复当前仍是本操作新字节的目标；原先 absent 的文件也只有仍为本次字节才可删除。外部后来修改、删除或无法验证的备份均保留并标记 RECOVERY_REQUIRED。硬中断无法依靠 finally，下一进程通过非终态 journal 阻止盲重启。恢复入口按实际 journal 状态受控续办或回滚；本模块不自动猜测续做，也不提供“强制覆盖”开关。

锁只协调采用本协议的写者，无法阻止任意外部编辑器在两次检查之间修改文件。当前验证覆盖进程终止和注入文件操作异常；不能据此宣称已证明断电后的磁盘一致性或部署了 ACL。

## 幂等与完成边界

committed 重跑须为同一 operation 和复核记录引用，复核记录字节摘要、原 result 摘要、明确目标清单及所有当前目标新摘要均一致，才返回原回执，不再写正式资产或日志。任何目标后来变化返回 APPLIED_STATE_CHANGED；记录丢失/损坏须恢复处理。已提交回放不再比较被自身落位改变的旧 baseline，也不以后来升级的工具指纹重新解释历史成功；新事务仍须通过当时最终视图的全部当前绑定检查。

成功表示本地 stable 字节落位，回执 `index_activated=false`。这不等于已构建/激活索引、已检索到知识、已合入主干或已推送。模块开发的 Git 合入及推送由有发布授权的开发流程独立记录实际 SHA。
