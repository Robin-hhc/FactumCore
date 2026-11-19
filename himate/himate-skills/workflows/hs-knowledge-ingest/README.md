# 知识入库 Workflow

在本次选定范围内串行处理待办。每批处理一个来源的变化或剩余阅读范围。P5 成功后回 P1，P1 扫描该范围无待办时汇总。首节点确认知识根、执行端与已安装的工具入口，用 `knowledge doctor --knowledge-root <知识根绝对路径> --json` 校验。各节点沿用同一工具版本和知识根，在数据所在端执行。

| 节点 | Skill | 执行与交付 |
|---|---|---|
| P1 选文件 | source | `knowledge ingest scan` 交接本轮文件和关联卡。PDF、DOCX、XLSX 同时交接完整 Markdown、图像与候选索引 |
| P2 决策 | change-plan | 阅读本轮选定范围，按六决策处理并查重。`plan.md` 固定候选 ID 和正式路径，有文档阅读范围时写 `source_units` |
| P3 写卡 | view-materialize | 按既定 ID/路径和模板写完整候选，将条件、依据和有效旧知识保留在正文 |
| P4 审阅 | review | `ingest check` 核对计划、候选与文档范围，独立审阅本批事实、条件、知识保留和生命周期，问题回 P2/P3 |
| P5 入库 | apply | `ingest commit` 验证 P4 检查过的范围与候选，刷新关系及检索索引，登记本批覆盖。全文完成时保存成功 hash |

P4 是独立 reviewer，其余为 coder。普通更新保留原生命周期，局部过时不整卡退役。PDF、DOCX、XLSX 的候选正文最多 76,000 UTF-8 字节，P2 从候选起点选择一个连续范围。已审阅且无增量的范围也可登记覆盖。P5 执行失败时保留本批暂存以便直接重试。

`completed` 表示本批发布完成，随后继续 P1。`source_complete` 为 false 时，后续扫描会继续发现该来源的剩余范围。未指定来源时保持普通扫描，指定文件、目录或来源 ID 时沿用原始范围。解析配置、阅读预算与命令前缀沿用，`reprocess` 只在首次使用。P1 返回 `blocked` 或 P2 暂缓时，交代原因和剩余范围后结束当前任务。

每批按真实回执简要交接来源、实际范围和结果，最后汇总本次范围的处理情况。解析缓存可删重建，累计覆盖在正式来源登记中保留；P1/P5 清理保留 .build 根 README。Git 提交和推送另行授权。

实际节点和转移由 workflow.yaml 维护；layouts.yaml 只维护画布。操作细节由各 Skill 提供，WiFi 领域设计见知识根的 `docs-llm-wiki/HiMate知识库详细设计.md`。
