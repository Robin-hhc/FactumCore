# WiFi 知识入库 Workflow

一次处理一个新增、修改或删除来源。首节点从实际工作区确认知识根与执行端，在 Linux 原生目录运行仓内 CLI。

| 节点 | Skill | 执行与交付 |
|---|---|---|
| P1 选文件 | source | `knowledge ingest scan`，交接本轮文件和关联卡 |
| P2 决策 | change-plan | 读材料，六决策及新增主题查重；plan.md 固定候选 ID/正式路径，必要时决定标签或状态变化 |
| P3 写卡 | view-materialize | 按既定 ID/路径和模板写完整候选，将条件、依据和有效旧知识保留在正文 |
| P4 审阅 | review | ingest check 核对计划与候选 ID/路径，再独立审阅事实、条件、知识保留和生命周期，问题回 P2/P3 |
| P5 入库 | apply | ingest commit，刷新关系/检索索引，最后登记成功 hash |

P4 是独立 reviewer，其余为 coder。普通更新保留原生命周期，局部过时不整卡退役。暂缓不推进文件成功版本。P5 使用已审结果，不复检；失败保留暂存直接重试，重新执行 P1 会清理本轮暂存，因此重试时不回 P1。Git 提交和推送另行授权。

实际节点和转移由 workflow.yaml 维护；layouts.yaml 只维护画布。操作细节由各 Skill 提供，设计见领域[详细设计](../../../../himate/himate-knowledge-wifi-mp/docs-llm-wiki/知识库详细设计.md)。
