# 单文件入库与检索验证场景

以公开 CLI 的输入和结果验证业务行为；稳定的纯算法另保留直接预期。下表是当前覆盖责任，不要求恢复旧阶段图、票据或私有路径。

| 场景 | 必须观察到的行为 | 主要验证层 |
|---|---|---|
| 新增来源 / create | 一次只选一个文件；零关联卡也能交作者；新卡可建立引用 | `ingest/`、`integration/` |
| 修改来源 / update | 只改确实受影响的结论，保持卡 ID；完成后保存本次 hash | `ingest/` |
| merge / split | 目标卡、旧卡去向及替代关系按明确清单落位 | `ingest/` |
| deprecate | 保留原因与替代入口，更新引用和检索结果 | `ingest/`、`query/` |
| defer | 保留原因与待办，不把文件成功 hash 向前推进 | `ingest/` |
| 删除与读取失败 | 确实缺失才是删除；不能读取不等于删除；不自动删除所有关联卡 | `ingest/` |
| 同卡多文档与代码 | 更新一张卡后刷新它的全部引用关系，保留其他来源 | `catalog/`、`ingest/` |
| 源码插行、改体、符号删除 | 函数定位能随插行变化，删除/歧义有准确结果；旧证据不冒充当前实现 | `contracts/test_code_symbols.py`、`contracts/test_code_ref_contracts.py`、`ingest/` |
| 文档设计与代码实现 | 设计依据不自动成为实现事实；纯文档不强制补造代码引用 | `query/`、`ingest/` |
| purpose 和适用条件 | current/guidance/implementation/historical 按实际规则过滤；未知条件不当作匹配 | `query/test_scope.py`、公开查询回归 |
| 已审无增量 | 可以无卡完成，后续扫描不会反复选中同版本 | `catalog/`、`ingest/` |
| P4 返工 | 决策问题回 P2，成稿问题回 P3；新稿重新审阅 | `workflows/`、隔离流程调用 |
| P5 失败重试 | 保留本轮稿件，重试相同入库动作可完成；不先回 P1 清理 | `ingest/` |
| Git 旧文档 | 能取得确切提交中的旧原文；未提交且无副本时准确说明不可恢复 | `ingest/`、`integration/` |
| 清理暂存 | 新 P1 清理 `.build`，数据库与成功处理事实保留 | `ingest/`、`catalog/` |
| 来源稍后再变 | P5 保存 P1 记录的 hash，后续扫描仍能发现新的版本 | `ingest/` |
| 数据库重建 | 由正式卡和来源登记恢复双向关系及无卡成功事实 | `catalog/` |
| 工作区和诊断 | doctor 选择确切配置，拒绝无效或歧义映射；错误不创建目标仓 | `cli/`、`contracts/test_workspace_mapping.py` |
| Skill 安装 | 覆盖复制当前能力包，保留无关能力包，用选定 Python 执行 pip 安装 | `repo/tools/deploy/tests/test_install_skills.py`（模拟 pip） |

六决策的语义效果需要作者和独立 reviewer 在实际材料上核验；仅通过脚本不能证明自动知识蒸馏质量。Workflow 静态测试也不代表实际宿主执行过。

旧冻结计划、view/revision 引用链、passed 票据、CAS、备份恢复及索引 generation 前置已移出新流程，相应测试和专用夹具删除。原业务预期迁移到上表职责；与现行算法仍有关的 legacy 来源只读兼容检查继续保留。历史报告保存在本地 SDD，不以旧全量数字作为新架构验收标准。
