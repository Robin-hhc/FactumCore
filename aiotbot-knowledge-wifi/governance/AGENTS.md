# 治理资产入口

本目录维护 Schema、受控枚举、契约适配、模板、规范与来源锁；导航见 [index.md](index.md)。正式技术结论只进入 `../knowledge/`，原件只进入 `../docs-raw/`，系统设计和 SDD 在 `../docs-llm-wiki/`。

已有规则字节由 `framework.lock.yaml` 固定。修改受锁定资产时同步审查版本与摘要，不以 Schema 通过替代事实核验。`sources.lock.yaml` 当前是空登记，不表示已经捕获来源。

本目录位于 `aiotbot-knowledge-wifi/governance/`，本次只建设 WiFi。现行契约为 2.0，五个 contracts 模块实现纯解析与验证；全部代码、Schema、Profile、枚举、模板及规范均受规则锁约束。1.0 历史记录不静默迁移或重签。初始化纯契约不扫描、执行或写入业务资产。

节点执行能力在仓根 `skills/common/knowledge/`，生产与治理编排在 `workflows/common/knowledge/`，与 main 同级，统一版本管理。每个节点仅加载调用者固定摘要且已逐文件核验的领域契约，不从来源内容加载程序。当前实现和验收进度见 [knowledge-v2](../docs-llm-wiki/sdd/knowledge-v2/README.md)；knowledge-v1 保留历史身份。纯文档确认免代码 lint，代码本地/合入只读双门禁遵循领域 AGENTS；形状验证不认证人或证明代码语义。
