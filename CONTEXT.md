# 本项目术语与边界

- Workspace：配置、能力与流程的组织容器。本轮由 FactumCore 单仓承载；WiFi 领域根为普通子目录 aiot-wifi-knowledge/，业务代码仍按真实所属仓或导出身份登记。
- Card / Claim：卡片是知识返回对象；断言是卡内独立判断来源、适用性和有效性的单位。
- Target：芯片、侧别、源码绑定与构建条件的逻辑槽。首发 chip12/chip08/chip07c × host/device，共六槽；同芯片三组候选 pair 不代表已验证兼容。
- resolved / context_loaded：先正确定位，再实际读取入口；列出文件不等于加载，CLI 文件读取也不证明 Agent 已采纳。
- draft/stable/deprecated：生命周期；local/proposed/merged：集成身份；有效性独立记录，不合并为一个“已验证”状态。
- code_gate：本地检查后 stable，CI 最新代码只读复核。manual_document：真实人工确认后 stable，贡献者可自确认，不跑代码门禁。
- final-view / ChangeSet：拟落位确切字节及带基线的变更清单。确认与检查均绑定最终字节。
- generation：固定内容、规则和证据构建的不可变索引及正文副本。

上游参考是研究事实；本轮独立实现，不复制 CANNBot 代码或事实。当前真实源码路径、构建、宏和 pair 兼容条件未配置，不能把合成测试写成业务覆盖。
