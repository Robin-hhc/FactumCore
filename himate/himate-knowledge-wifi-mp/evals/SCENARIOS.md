# 单文件入库与检索验证场景

以公开 CLI 的输入和结果验证业务行为；稳定的纯算法另保留直接预期。下表是当前覆盖责任，不要求恢复旧阶段图、票据或私有路径。

| 场景 | 必须观察到的行为 | 主要验证层 |
|---|---|---|
| 新增来源 / create | 一次只选一个文件；零关联卡也能交作者；新卡可建立引用 | `ingest/`、`integration/` |
| 修改来源 / update | 只改确实受影响的结论，保持卡 ID、原路径和原生命周期；状态变化由 P2 决定，完成后保存本次 hash | `ingest/` |
| merge / split | 目标卡、旧卡去向及替代关系按明确清单落位 | `ingest/` |
| deprecate | 仅整卡失效时退役，保留原因与替代入口；默认不搜、开关包含、按 ID 可读；局部历史不整卡退役 | `ingest/`、`query/` |
| defer | 保留原因与待办，不把文件成功 hash 向前推进 | `ingest/` |
| 删除与读取失败 | 确实缺失才是删除；不能读取不等于删除；不自动删除所有关联卡 | `ingest/` |
| 同卡多文档与代码 | 更新一张卡后刷新它的全部引用关系，保留其他来源 | `catalog/`、`ingest/` |
| 源码插行、改体、符号删除 | 函数定位能随插行变化，删除/歧义有准确结果；旧证据不冒充当前实现 | `contracts/test_code_symbols.py`、`contracts/test_code_ref_contracts.py`、`ingest/` |
| 文档设计与代码实现 | 设计依据不自动成为实现事实；纯文档不强制补造代码引用 | `query/`、`ingest/` |
| 简洁卡正式召回 | 三必填卡、空代码引用及缺省标签可默认命中；候选入库前不参与搜索，不补造 Claim、用途或范围 | `catalog/`、`ingest/`、`query/` |
| 整卡词项与标签 | 词项可分布于不同段落，全部查询词组与 AND 标签须满足；固定字段权重，同词项不因旧 Claim 数量重复加分 | `query/`、公开查询回归 |
| 完整读取与旧卡 | 原始 metadata、完整正文、规范引用及来源保留；旧 scope/claims/历史依据可见，旧 draft 不自动升级或默认搜索 | `catalog/`、`query/` |
| 旧调用参数 | 显式 purpose/context 在搜索或读卡前报 QUERY_PARAMETERS_REMOVED、退出码 2，不生成正常命中报告 | `cli/`、`query/` |
| 搜索缓存升级 | 无卡改动也按格式版本升级；失败回滚，卡与快照字节、来源 ID、成功处理版本不变 | `catalog/`、`query/` |
| 已审无增量 | 可以无卡完成，后续扫描不会反复选中同版本 | `catalog/`、`ingest/` |
| P4 返工 | 决策问题回 P2，成稿问题回 P3；新稿重新审阅 | `workflows/`、隔离流程调用 |
| P5 失败重试 | 保留本轮稿件，重试相同入库动作可完成；不先回 P1 清理 | `ingest/` |
| Git 旧文档 | 能取得确切提交中的旧原文；未提交且无副本时准确说明不可恢复 | `ingest/`、`integration/` |
| 清理暂存 | 新 P1 清理 `.build`，数据库与成功处理事实保留 | `ingest/`、`catalog/` |
| 多格式与图文材料 | Docling 交付正文、结构、独立图片和原文定位；OCR 与原图共同可读，外链不自动抓取、缺口可见 | `contracts/test_document_parser.py`、`ingest/test_document_extraction.py` |
| 同轮材料与历史兼容 | P4 复用 P1 固定产物；损坏不静默重转；旧 snapshot 使用准确旧字节与原 extractor | `ingest/test_document_extraction.py`、`ingest/test_legacy_document_refs.py` |
| 独立来源阅读 | 按页提取不清 `.build`、不推进处理 hash；UUID 隔离、消费后精确释放，续期/过期回收不误删有效或正在转换任务 | `contracts/test_source_read.py`、`ingest/test_source_extract.py` |
| 转换与查询共存 | 文档转换不持有 Catalog 写事务，长转换期间仍可搜索和读正式卡 | `ingest/test_document_extraction.py`、`ingest/test_source_extract.py` |
| 图文公开闭环 | Office 原图导出、P4 检查、P5 清理、query/read 与独立提取/释放均通过实际 CLI 入口 | `integration/test_document_materials_cli.py` |
| 来源稍后再变 | P5 保存 P1 记录的 hash，后续扫描仍能发现新的版本 | `ingest/` |
| 数据库重建 | 由正式卡和来源登记恢复双向关系及无卡成功事实 | `catalog/` |
| 工作区和诊断 | doctor 选择确切配置，拒绝无效或歧义映射；错误不创建目标仓 | `cli/`、`contracts/test_workspace_mapping.py` |
| Skill 与 Workflow 模板安装 | 先向选定 Python 执行一次锁定依赖的 pip 安装，再删除本次全部同名包目录，最后复制全部新包；pip 失败不动旧包，同名包完整替换，源码和目标根其他包保留 | `repo/tools/deploy/tests/test_install_skills.py`（模拟 pip） |

六决策的语义效果需要作者和独立 reviewer 在实际材料上核验；仅通过脚本不能证明自动知识蒸馏质量。Workflow 静态测试也不代表实际宿主执行过。

旧来源与卡片的有效只读兼容继续验证。历史报告保存在本地 SDD，不以旧全量数字作为当前验收标准；整卡命中不证明结论适用、实现完成或宿主验收通过。
