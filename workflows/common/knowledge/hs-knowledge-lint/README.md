# WiFi 知识治理巡检 Workflow

按串行运行设计：L1 同步、L2 找待办、L3 刷索引、L4 汇总；内容处理复用 P1—P5，P4 仍是独立 reviewer。外部系统负责周期触发。

L2 的 patrol plan 不创建暂存，返回真实 next_file.source_id；P1 用该 ID 准备一份 raw 或登记代码文件。P5 成功后回 L2，逐文件继续处理。暂缓时结束当前处理并在 L4 说明剩余事项，不推进其成功 hash、不立即重复选择同一文件。

仅索引问题进入 L3；无待办进入 L4。L4 统计剩余事项，不另建全库水位。同步仅执行配置的 argv/cwd；内部 MM 只适配同步，子仓历史使用原生 Git。

没有嵌套 Workflow，也不并发运行另一个 ingest。详细流程见领域[详细设计](../../../../himate/himate-knowledge-wifi-mp/docs-llm-wiki/知识库详细设计.md#31-lint-的检查流程)。
