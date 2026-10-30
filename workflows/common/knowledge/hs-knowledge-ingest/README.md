# WiFi 知识入库 Workflow

六个执行节点按 P1–P6 编号；P1 在同一来源节点完成观察与备料。每个节点只加载自己的指令Skill，P5独立于来源准备。

命令表以 Windows 为例，在实际知识根执行；POSIX 将 `.\knowledge.cmd` 换成 `sh ./knowledge.sh`。已注册入口时也可用 `knowledge`。

| 节点 | Skill | 主要命令 | 交付 |
|---|---|---|---|
| P1 来源准备 | hs-knowledge-source | .\knowledge.cmd source | scan_ref、material_ref或真正unchanged |
| P2 作者判断 | hs-knowledge-change-plan | .\knowledge.cmd change-plan | semantic_plan_ref |
| P3 完整稿件 | hs-knowledge-view-materialize | .\knowledge.cmd view-materialize | view_ref |
| P4 独立审阅 | hs-knowledge-review | .\knowledge.cmd review | 实际审阅、固定检查及候选查询结果 |
| P5 转写记录 | hs-knowledge-record | .\knowledge.cmd record | 待发布ingest_record_ref |
| P6 发布收尾 | hs-knowledge-apply | .\knowledge.cmd apply --action batch | publication/completion及实际batch_complete |

P4由宿主安排独立reviewer，其余节点为coder。角色、转移和交棒由宿主落实；Skill说明当前动作，CLI核实际业务输入，不依赖上游passed票据。

新执行采用新操作。来源prepared进入P2，完整且确无事项才unchanged结束；明确补料直接source prepare。P4缺料回来源、判断错回P2、稿件错回P3，新候选重新审阅。计划已冻结却尚无view的不可变输入停点按实际诊断保留，不伪造前序视图。

P1—P5仅写本批暂存，P6才发布正式内容与处理事实。published与batch_complete分开报告；已发布但收尾或清理未完时只续办原批次。真正完成后才结束，Git提交、CI和合入分别处理。

首节点复用项目与执行端信息；缺项时从当前工作区的实际 `AGENTS.md`、`config.yml` 定位，位置不明确再询问用户。各节点在实际知识根调用仓内启动器。Workflow副本升级后核对P4的review与P5的record绑定。`workflow.yaml`维护节点及分支，`layouts.yaml`维护画布；详细操作以对应Skill为准。
