# 治理资产入口

本目录维护 Schema、受控枚举、契约适配、模板、规范与来源锁；导航见 [index.md](index.md)。正式技术结论只进入 `../knowledge/`，原件只进入 `../docs-raw/`，系统设计和 SDD 在 `../docs-llm-wiki/`。

已有规则字节由 `framework.lock.yaml` 固定。修改受锁定资产时同步审查版本与摘要，不以 Schema 通过替代事实核验。`sources.lock.yaml` 当前是空登记，不表示已经捕获来源。

本目录位于 `aiotbot-knowledge-wifi-mp/governance/`，本次只建设 WiFi。记录契约保持 2.0；contracts 的 validation、knowledge、source_resources、records、checks 与 indexing 共用安全解析、跨文件验证、检查报告及完整索引核验。规则能力版本与全部代码、Schema、Profile、枚举、模板及规范均受规则锁约束；不兼容返回未完成。历史记录不静默迁移或重签。纯契约装载不扫描、执行或写入业务资产。

节点执行能力在项目根 `../../skills/common/knowledge/`，单一 ingest 编排在 `../../workflows/common/knowledge/`，由 FactumCore 统一管理。每个节点仅加载调用者固定摘要且已逐文件核验的领域契约，不从来源内容加载程序。流程和节点文件分工见[概要与详细设计](../docs-llm-wiki/知识库详细设计.md)，实现与验收记录见 [SDD](../docs-llm-wiki/sdd/knowledge-v3/README.md)。

P4 完成确切视图的真人确认或代码语义核验；P5 调用独立只读 lint，纯文档代码项不适用，结构／来源／导航／临时索引仍检查。P6 登记处理记录，P7 同批事务入库。上库只运行[固定 CI](specs/ci-runner.md)，复用 checks/indexing，不加载 Agent、Workflow、catalog、私人 `.build` 或原始确认事件，不修卡、不切换活动索引。代码内容由独立 Agent 复核并留存逐 Claim 理由和依据；脚本核对记录、作者回避及确切对象绑定，不要求代码复核者公钥或密码学签名，也不认证 Agent 身份或知识语义。纯文档真人动作、共享发布回执仍按各自规则验证，跨机查询还须核对实际 Git 内容绑定。
