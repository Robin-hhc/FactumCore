# 知识库设计对齐与实现

本轮以用户确认的[详细设计快照](baseline/知识库详细设计.md)为唯一规格基线，原文 SHA-256 为 `32df6c9505f3f7c6e8220f90a02a030641d5c9f39d0402ac80154b6556ad2f54`。本目录记录实现筛查、任务、测试与验收；不向面向读者的设计文档写入开发进度。

```mermaid
flowchart LR
    B[冻结设计和现状] --> A[全量实现筛查]
    A --> D[差异与任务]
    D --> R[公开接口失败用例]
    R --> I[分组实施与验证]
    I --> V[集成回归与独立复核]
    V --> E[验收事实和外部待办]
```

入口：[需求与差异](requirements.md)、[实现设计](design.md)、[修改落点](changes.md)、[任务](tasks.md)、[测试计划](test-plan.md)、[本地验收](acceptance.md)、[基线身份](baseline.json)。`records/implementation-before.json` 保存修改前实现指纹；`records/history-before.json` 保存历史工件指纹，v1/v2 不重写。

本轮不增加此前暂缓的新 search 索引过期检查，不更换 Workflow 引擎，不机械合并节点 Skill，不接入虚构业务代码、Target 或真人确认。本地合成验证与真实宿主、真人、六 Target、远端 CI 和权限验收分别报告。
