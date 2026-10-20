# Knowledge v1 SDD 入口

本 SDD 细化用户确认的[主设计《AIoTBot知识库架构设计》](../../AIoTBot知识库架构设计.md) §5.3 + 第 11 章及[《知识库详细设计》](../../知识库详细设计.md)v2.0；源文件实际摘要固定在 [baseline.json](baseline.json)。这些是用户批准的工作区设计文件，不能用较旧 Git HEAD 替代其内容。

当前部署由用户指定为 FactumCore 单仓，目录按主设计 §5.3：仓根 `main/` 为空，`skills/`、`workflows/` 仅保留四个 Skill 和两个 Workflow 的空骨架；唯一领域为 `aiot-wifi-knowledge/`。SDD 位于该领域的 `docs-llm-wiki/sdd/knowledge-v1/`。现有共享实现、工具和依赖已移至仓外，当前 checkout 不可运行历史 CLI。最新布局、归档身份与执行状态见[布局与部署记录](records/workspace-layout-20261020.md)和 `traceability.json.current_deployment`；[单仓迁移记录](records/single-repo-migration.md)保留当时事实。用户级 AGENTS 由用户自行配置，不纳入开发、安装、升级或托管验收；全局 Skill 安装可见性、workspace-registry 定位、仓内 AGENTS 实际加载和仓外宿主实测仍按 T23/T24 交付。

## 阅读和执行顺序

1. [需求规格](requirements.md)：R01–R18、失败边界、首发范围。
2. [全局模块设计](design.md)和[九模块目录](module-map.md)：逐模块 spec/design/tasks，唯一主文件归属。
3. [任务与依赖 DAG](tasks.md)：T01–T28，每票有 Blocked by、具体交付、验收和失败返回。
4. [测试与验收计划](test-plan.md)：原设计 E01–E34、合成机制、宿主触发和真实业务分别验收。
5. [开发记录](records/README.md)：red/green、环境、审查与验收事实；没有记录的能力不写已完成。

[traceability.json](traceability.json) 逐项关联 **18 需求 → 9 模块 → 148 路径 → 34 验收 → 28 任务**。其中未来 sources 三项延期，运行产物、实例和外部源码按规则生成/登记，不能为了凑齐目录制造事实。

## 当前批次

[T01](tickets/T01.md) 和 [T02](tickets/T02.md) 曾完成首批基础，历史接口见[first-slice](first-slice.md)。T03 → T05 → T06 → T07 曾在合成资料上完成 raw 捕获、候选、真人终端确认与 stable 事务验证，见[当批最终验收](records/T07-verification.md)。历史 230 项合成测试不证明当前骨架可执行，也不关闭宿主隐式触发、真实业务、聊天适配、完整恢复或检索验收。各票历史状态、范围和后续依赖见任务入口。

[raw 文档手工操作手册](document-chain-usage.md) 保留历史 capture/load-capture、plan/materialize、真人 confirm/narrow 和本地 apply 的接口、范围与错误处理，不是当前 checkout 的可执行指南。完整 Skill/Workflow 自动编排仍按 T20/T21 开发。

## 变更和状态规则

规格、任务、测试和代码必须可追溯。变更字段/接口时先记录需求影响，补失败测试，再修改及审查；若改变已批准架构，则回到固定来源设计记录决策，不让实现静默改约束。

任务表和 `traceability.json.tasks` 保留已有开发验收状态；当前执行/部署状态以 `traceability.json.current_deployment` 及最新布局记录为准。ticket 和模块文档是行为要求，不能单靠勾选判通过。真实业务输入缺失、外部授权或宿主安装未验证，保留 external_validation_required。版本锁保证本地字节一致性，不能替代受信 CI 或访问控制。
