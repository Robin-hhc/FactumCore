# WiFi 知识入库 Workflow

一次处理一个新增、修改、删除来源或 PDF 页批。首节点从实际工作区确认知识根与执行端，在 Linux 原生目录运行仓内 CLI。

| 节点 | Skill | 执行与交付 |
|---|---|---|
| P1 选文件 | source | `knowledge ingest scan`，交接本轮文件和关联卡；PDF 交接起点、宽候选与页索引 |
| P2 决策 | change-plan | 读本轮完整范围，六决策及新增主题查重；plan.md 固定候选 ID/正式路径，PDF 显式写 source_pages，必要时决定标签或状态变化 |
| P3 写卡 | view-materialize | 按既定 ID/路径和模板写完整候选，将条件、依据和有效旧知识保留在正文 |
| P4 审阅 | review | ingest check 核对计划、候选与 PDF 范围，再独立审阅本批事实、条件、知识保留和生命周期，问题回 P2/P3 |
| P5 入库 | apply | ingest commit，刷新关系/检索索引，合并 PDF 本批覆盖，仅全文完成才登记成功 hash |

P4 是独立 reviewer，其余为 coder。普通更新保留原生命周期，局部过时不整卡退役。PDF 默认按字量准备宽候选，无默认页数帽；P2 按自身上下文、图表、条款和产卡量自选实际结束页，无须读完候选，也不能跳起点。实际范围经评估、P4 和 P5 后才记覆盖，无增量页也可完成。P5 只核对机械范围约束，不重复质量审阅；暂缓或失败不推进覆盖，失败保留暂存直接重试，不回 P1 清理。

completed 表示本批发布完成。回执 source_complete=false 时，该 PDF 尚有未评估页，下次普通运行从剩余范围继续；不要宣称全文完成。解析缓存可删重建，累计覆盖在正式来源登记中保留；P1/P5 清理保留 .build 根 README。Git 提交和推送另行授权。

实际节点和转移由 workflow.yaml 维护；layouts.yaml 只维护画布。操作细节由各 Skill 提供，设计见领域[详细设计](../../docs-llm-wiki/知识库详细设计.md)。
