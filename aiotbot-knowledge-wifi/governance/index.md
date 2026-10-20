# 治理导航

| 位置 | 职责 |
|---|---|
| `framework.lock.yaml` | 固定 2.0 契约代码、Schema、模板及声明的确切字节摘要 |
| `sources.lock.yaml` | 来源资源和快照登记，当前为空 |
| `schemas/` | 字段形状、Profile 与公共受控值 |
| `contracts/` | 五个纯领域 API，统一解析、路径、来源、Claim、范围、关系与记录契约；节点程序通过受信摘要加载 |
| `templates/` | 七类卡、导航与人工确认模板 |
| `specs/` | 卡片、来源、记录和生命周期规范 |

目标文件、开发要求与验收见[详细设计](../docs-llm-wiki/知识库详细设计.md)，当前实现以 [knowledge-v2](../docs-llm-wiki/sdd/knowledge-v2/README.md) 的逐项证据为准；v1 布局及成绩只代表历史版本。
