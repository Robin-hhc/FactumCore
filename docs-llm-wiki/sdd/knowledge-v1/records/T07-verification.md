# T07 文档 stable 事务与本批验收

日期：2026-10-20。T06 已发布 FactumCore main `270fe6c7c32e8e7da6bc361fea96215e2dff4c99`，远端 SHA 已实际核对一致。

## 实现与路径

`ingest apply` / transactions.apply_document 只接受单卡 create/update 的确切人工接受视图。跨进程 OS 锁内核固定 Review 字节、当前基线 CAS、目标与来源字节、全 knowledge 的 Card/Claim ID、关系目标及 requires/replacement 无环；原件和无关 dirty 文件不在写入清单。其余计划明确返回 DEFERRED_OPERATION。

备份、backup-manifest、write-ahead journal 和原结果唯一持久位于 `logs/operations/<operation_id>/`。SDD 为原设计 .build/transaction 与扁平 operation 记录加 implementation_path 映射：这是清理候选后仍保留恢复材料的内部落实，未建立两套 journal 或第二个正文根。

先核备份与 prepared journal，再写同目录临时文件并 flush/fsync、替换、记进度；只有所有目标和回执复核成功才 committed。普通失败只回滚仍由本事务拥有的新字节；未尝试目标、外部后来编辑和损坏恢复材料均保留并 RECOVERY_REQUIRED。真实子进程持锁/终止用例通过；这不是断电存储一致性或 ACL 验收。

committed 重跑核相同 review、实际结果摘要和目标新字节，只读返回原回执。历史 committed result 缺失/损坏或任一非终态 journal 阻断新写者。完整 recover 入口仍 T08，跨卡应用 T09，索引 T10；本次 index_activated=false，不隐式 Git/发布、不调用文档代码 lint。

## Red / green 与两轴审查

事务初始缺模块 red；独立开发后 37 项通过，含 Windows 真子进程 OS 锁、硬 kill、CAS、全域冲突、写前备份、各写入阶段故障、回滚保留外部编辑、损坏日志及严格幂等。公共端到端另验证 capture→plan→materialize→测试专属终端确认→CLI apply、版本目录更新和重放，不使用伪造生产人工记录。合成人动作/记录明确标 synthetic，仅存临时 K。

Standards 与 Spec 独立审查固定 `0674f98328cc76575fbb36323545dfe50120b00d`：发现捕获/验证 Review 分读导致 A→B→A 错绑、历史成功结果缺失漏检、复杂计划缺 changeset 返回 TOOL_ERROR；主执行器另发现规定目录外卡片被漏扫。新增 **8 项实际 red**（含五种 planned-only 决策）后修复：验证同份 Review bytes、完整历史结果门、先判决策、扫描整个 knowledge 并核 Profile 路径；另补非对象 journal 防御。修复初轮有一项诊断码顺序回归，调整后全部通过。

最终针对集合 **49 passed / 38.39s**。两轴复核固定 `e0466505487ed1ec7542f40409e344b60e6a6427` 均 closed；Standards 2 项、Spec 6 项独立复验通过。该固定快照的干净 checkout 完整回归 **230 passed / 143.65s，零跳过**；SDD、Ruff、格式检查及 compileall 均通过。最后仅补本记录、任务状态与操作说明，无后续代码变更。

- [完整 JUnit](T07-clean-junit.xml)
- [环境、命令与固定代码摘要](second-batch-verification.json)
- [可运行手工链说明](../document-chain-usage.md)

## 本批结案边界

T03/T05/T06/T07 在合成机制范围 verified，E09/E10/E15/E03/E11/E12/E13/E14/E17 保留相应 partial 边界。未导入真实 raw、未生成真实知识卡，未验证真实六 Target 工程、宿主隐式 Skill、聊天确认 adapter 或权限部署。T20/T21 完整自动工作流仍计划中。

本票已单独提交推送 main `8ee6a95fa5e841e354ae76cc77f482de8975de7b` 并核对远端；逐模块实际身份见[发布回执](publication.json)。业务摄入的 apply 本身不包含这些 Git 动作。
