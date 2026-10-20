# FactumCore 单仓部署迁移

完成日期：2026-10-20。用户明确指定沿用 `https://github.com/Robin-hhc/FactumCore`，在仓根维护 `aiot-wifi-knowledge/`、`skills/`、`workflows/` 等，现有 `docs/` 对应 `docs-llm-wiki/`。此前两个新建本地开发仓不再分别配置远端或作为本轮发布根。

## 范围与来源

- 将原 docs/ 的 52 个现有文件整体 Move-Item 到 docs-llm-wiki/；执行前核对来源与目标的绝对路径，确认目标不存在，迁移后逐文件 SHA-256 与迁移前一致。
- 仅导入框架提交 `2126a73f8a5e764460258a2abc82c92f3d31beb2` 与 WiFi 提交 `898ece0a3a1721a77910aed3518e0fa189f50860` 的已跟踪 HEAD blob，共 98 个文件；框架 docs/ 映射到 docs-llm-wiki/，领域文件进入根 aiot-wifi-knowledge/。
- AGENTS、README、ignore 与 attributes 按当前单仓融合。未复制任一嵌套 .git、venv、构建产物或来源目录中的未提交新实现。原开发目录和旧 aiot-knowledge/ 保留原身份。
- 配置相对路径现在以 FactumCore 根 config.yml 为基准；知识根仍为 aiot-wifi-knowledge。六 Target/三 pair 逻辑登记与 unknown 状态保持。

完整迁移前文件摘要、原工作区状态（仅路径）、导入文件清单及来源摘要见 [single-repo-migration.json](single-repo-migration.json)。迁移完成后，原 52 个文件中的 47 个继续保持原字节；另外 5 个是授权更新的文档入口与部署决议：docs-llm-wiki/AGENTS.md、设计文档/AGENTS.md、设计文档/README.md、aibot.md、知识库详细设计.md。

主设计和详设仅插入当前单仓部署决议一段；去掉该段即可重现迁移前的完整文件摘要，未改详设 1.1 流程图。baseline.json 同时保留原来源路径和摘要，新增当前相对路径、实际摘要及部署决议引用。149 路径、18 需求、9 模块、34 验收、28 任务与 49 依赖边保持原基数。

## 无关未提交材料的保留

以下文件迁移前后 SHA-256 相同。完整 52 文件清单在 JSON；它们的未提交身份不因目录迁移变成发布授权，提交时应从原 HEAD 映射已有研究文件，而非批量暂存当前 dirty 研究内容。

| 新路径（均位于 docs-llm-wiki/） | SHA-256 |
|---|---|
| research/aiotbot-knowledge-feasibility-and-detailed-design-2026-10-18.md | `613404730f5c02368a35ded5690a3837d3b4fedd688b0fd86f5452cf26b4ab91` |
| research/w3-code-kb-cases.md | `fe2c10940757ae9b1903e219a62799b1a9c0ce3a1968b379379259ba775838bb` |
| research/w4-tool-selection.md | `27cd7d261eb3ec6508c08d4a88d38c11665d99d5fbd09435355980210ad5b4b2` |
| experiments/hi1105-a-b-benchmark.md | `75a5a1b7746c35ae49d81d4468eddb2beb62a43a9564bd086bc12f4968bbd1aa` |
| research/a-b-c-industry-evidence.md | `2f122d46bcb7dffd101aac37266ad97912b5897adad808dfa0f1c6ce787aadbe` |
| research/group-isolated-knowledge-workspace-design-2026-10-08.md | `d22c5418b431d1f582dbabbb352ce86810ce98f4b3051ee2c90e7591abbb540d` |
| research/industry-llm-wiki-comparison-2026-10-10.md | `f2569f2441732b9bf326386b8f7bd669d4f4b8d24ffebe5bd306ff9c196109c5` |
| research/llm-wiki-workspace.md | `938b56b3c0fc6a932be3fa3a138e5d2857ca4344c7618c2216bc0f7b43f076f3` |
| research/workspace-implementation-decision.md | `80a52a11cf9ba9a2277c7efeed6831ed001577527861ccc6168ac86442967b77` |

未读取 benchmark gold 内容，未恢复既有 benchmark 删除，未处理 analysis/ 或 .scratch/。新 AGENTS 是当前单仓说明，没有恢复用户已废止的旧指令。

## 实际验证与边界

在 FactumCore 根执行 tools/validate_sdd.py，通过来源摘要、追踪关系与 DAG 校验。公开 CLI workspace contract 校验成功，business_ready=false，六 Target 继续 unknown。

显式执行迁入的 T01/T02 三份测试：test_contracts.py、test_scope_conditions.py、test_workspace.py，结果 **69 passed，27.01 秒**；[JUnit](single-repo-baseline-junit.xml) 摘要为 `52e4dff1a776626dbd93d2e0ae28d92212e453a58ead69d62aeae6fcec0cea0a`。使用原开发目录已固定依赖的 Python 3.12 虚拟环境作为解释器，测试 cwd 和被测文件均为 FactumCore 根。迁移过程中其他 Agent 已在根继续开发新模块；这不是新一批代码的冻结快照验收。

此前一次无指定文件的测试发现正在开发的 changes.py 尚未接入 sources.py，collection 因 ImportError 中断；随后仅运行上述 3 份基线测试。未将并发未完成模块的收集失败记作迁移通过或新模块功能 red。首批原 records 中的命令、目录、提交和成绩保持历史原文，未改写为本次运行。

单仓变更只调整当前开发与 Git 发布布局。共享程序与领域资产仍分职责，未来框架发行须显式排除组内原件、卡、来源锁、运行日志和索引。目录、ignore 与同仓提交不提供 ACL；没有借此宣称业务接入、人工确认、stable 事务、知识检索或宿主隐式触发已完成。

本记录建立时未执行暂存、提交、合入或推送；这些由模块交付记录实际发生后补充，不能从本次文件迁移推断已发布。
