# Knowledge v1 SDD 入口

本 SDD 细化用户确认的主设计 §5.3 + 第 11 章及《知识库详细设计》v2.0；源文件实际摘要固定在 [baseline.json](baseline.json)。这些是用户批准的工作区设计文件，不能用较旧 Git HEAD 替代其内容。

当前部署由用户指定为 FactumCore 单仓：仓根 skills/、workflows/、config.yml 与 aiot-wifi-knowledge/ 一并版本管理，原 docs/ 迁至 docs-llm-wiki/。迁移过程与历史证据边界见[单仓迁移记录](records/single-repo-migration.md)；本次布局调整不提升任何业务或宿主验收状态。

## 阅读和执行顺序

1. [需求规格](requirements.md)：R01–R18、失败边界、首发范围。
2. [全局模块设计](design.md)和[九模块目录](module-map.md)：逐模块 spec/design/tasks，唯一主文件归属。
3. [任务与依赖 DAG](tasks.md)：T01–T28，每票有 Blocked by、具体交付、验收和失败返回。
4. [测试与验收计划](test-plan.md)：原设计 E01–E34、合成机制、宿主触发和真实业务分别验收。
5. [开发记录](records/README.md)：red/green、环境、审查与验收事实；没有记录的能力不写已完成。

[traceability.json](traceability.json) 逐项关联 **18 需求 → 9 模块 → 149 路径 → 34 验收 → 28 任务**。其中未来 sources 三项延期，运行产物、实例和外部源码按规则生成/登记，不能为了凑齐目录制造事实。

## 当前批次

[T01](tickets/T01.md) 和 [T02](tickets/T02.md) 已完成首批可运行基础，具体接口见 [first-slice](first-slice.md)。这不将整套 I0/I1、E01/E02 或隐式 Skill 触发写作已通过。当前按 T03 → T05 → T06 → T07 打通 raw 捕获、候选、人工确认和 stable 事务；每票以实际测试、审查和发布记录更新状态。

## 变更和状态规则

规格、任务、测试和代码必须可追溯。变更字段/接口时先记录需求影响，补失败测试，再修改及审查；若改变已批准架构，则回到固定来源设计记录决策，不让实现静默改约束。

任务状态以 traceability.json 为准；ticket 和模块文档是行为要求，不能单靠勾选判通过。真实业务输入缺失、外部授权或宿主安装未验证，保留 external_validation_required。版本锁保证本地字节一致性，不能替代受信 CI 或访问控制。
