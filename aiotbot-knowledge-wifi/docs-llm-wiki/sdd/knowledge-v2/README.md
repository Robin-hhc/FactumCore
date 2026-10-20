# WiFi节点能力 SDD v2

本轮批准18个节点Skill与两个Workflow，当前设计基线为[详设v4](../../知识库详细设计.md)。本SDD独立于[knowledge-v1](../knowledge-v1/README.md)，不改其字节、路径、记录或通过身份。

公开运行合同：[implementation-protocol.md](implementation-protocol.md)。

阅读：[需求](requirements.md) → [设计](design.md) → [模块](module-map.md) → 当前ticket → [测试计划](test-plan.md) → [实际记录](records/README.md)。[基线](baseline.json)保留规划时设计来源字节，当前运行与测试源码身份见[实现manifest](records/implementation-manifest.json)；[追踪](traceability.json)保存需求/模块/文件/票/验收与DAG。

18个节点Skill与两个Workflow直接在FactumCore根skills/与workflows/开发，和main同级，使用当前远端；无嵌套.git，不发布个人安装路径。新票据最初为pending；当前T201–T210已按实际测试、审查与发布证据完成开发，T211保留真实外部缺口。静态文档通过只关闭规划文档检查，不关闭运行或真实外部验收。

| 任务 | 行为交付 | 模块 | 依赖 | 当前状态 |
|---|---|---|---|---|
| [T201](tickets/T201.md) | 契约与运行协议 | M01 | 无 | complete |
| [T202](tickets/T202.md) | 发现与项目绑定 | M02 | T201 | complete |
| [T203](tickets/T203.md) | raw捕获与可恢复快照 | M03 | T202 | complete |
| [T204](tickets/T204.md) | 六决策候选与精确视图 | M04 | T203 | complete |
| [T205](tickets/T205.md) | 真实动作、事务与恢复 | M05 | T204 | complete |
| [T206](tickets/T206.md) | 索引、查询与回归激活 | M07 | T205 | complete |
| [T207](tickets/T207.md) | 维护事件与双水位 | M08 | T203, T205, T206 | complete |
| [T208](tickets/T208.md) | 代码捕获与只读双门禁 | M06 | T202, T204, T205 | complete |
| [T209](tickets/T209.md) | 两个Workflow和节点包 | M09 | T202, T203, T204, T205, T206, T207, T208 | complete |
| [T210](tickets/T210.md) | 节点集成与开发交付 | M09 | T201, T202, T203, T204, T205, T206, T207, T208, T209 | complete |
| [T211](tickets/T211.md) | 真实外部环境验收 | M09 | T210 | pending |

先打通T201→T202→T203→T204→T205→T206的raw纵向；T207维护与T208代码可按依赖并行，再做T209编排/T210集成。T211需要真实外部输入，不能由fixture关闭。

当前结果见[开发验收](records/development-acceptance-20261021.json)和[发布](records/publication-20261021.md)。
