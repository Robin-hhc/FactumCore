# HiMate 知识库开发文档

| 文档 | 内容 |
|---|---|
| [开发指南](../CONTRIBUTING.md) | 源码、治理规则、Skills 和 Workflows 的维护 |
| [安装与部署](../tools/deploy/README.md) | 执行端依赖、能力安装目录和 OCR 模型 |
| [面板 CLI 契约](面板CLI契约.md) | OpenFlow 宿主的读取、分页和原件投递 |
| [治理规则](../governance/index.md) | 知识卡字段、来源、生命周期与固定检查 |
| [测试与验收](../evals/README.md) | 回归入口、测试分组和验收范围 |

命令参数与节点交接字段维护在相应 Skill 的 `references/`。本地开发设计、实现调研和历史验证记录放在 Git 忽略的 `sdd/`。用户操作与系统设计见所用知识仓的 `docs-llm-wiki/README.md`。
