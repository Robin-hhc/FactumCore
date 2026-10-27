# 治理资产入口

本目录维护 Schema、受控枚举、契约适配、模板、规范与来源锁；导航见 [index.md](index.md)。正式技术结论只进入 `../knowledge/`，原件只进入 `../docs-raw/`，系统设计和 SDD 在 `../docs-llm-wiki/`。

已有规则字节由 `framework.lock.yaml` 固定。修改受锁定资产时同步审查版本与摘要，不以 Schema 通过替代事实核验。`sources.lock.yaml` 当前是空登记，不表示已经捕获来源。

本目录位于 `himate-knowledge-wifi-mp/governance/`，本次只建设 WiFi。记录契约保持 2.0；contracts 的 validation、knowledge、source_resources、records、checks 与 indexing 共用安全解析、跨文件验证、检查报告及完整索引核验。规则能力版本与全部代码、Schema、Profile、枚举、模板及规范均受规则锁约束；不兼容返回未完成。历史记录不静默迁移或重签。纯契约装载不扫描、执行或写入业务资产。

节点能力与 ingest 编排的开发分发源码在项目根 `../../skills/common/knowledge/` 和 `../../workflows/common/knowledge/`；实际部署在 Agent 自己的目录，使用执行机器的全局 Python 与同级公开 Skill 入口。首次准备在 workspace Skill，节点与固定 CI 不依赖项目根能力目录或 catalog 登记。节点默认加载实际规则锁并逐文件核验，显式摘要可固定本次规则；不从来源内容加载程序。流程和节点文件分工见[概要与详细设计](../docs-llm-wiki/知识库详细设计.md)。项目自身的实现与验收记录位于本地 `../docs-llm-wiki/sdd/`，由 Git 忽略，不作为领域规则、知识来源或部署输入。

P4 完成确切视图的独立 Agent 内容复核及适用代码核验；P5 调用独立只读 lint，纯文档代码项不适用，结构／来源／导航／临时索引仍检查。P6 登记处理记录，P7 同批事务入库。上库只运行[固定 CI](specs/ci-runner.md)，复用 checks/indexing，不加载 Agent、Workflow、catalog、私人 `.build` 或私人执行记录，不修卡、不切换活动索引。代码内容由独立 Agent 复核并留存逐 Claim 理由和依据；代码复核 Skill 核对本次记录、逐 Claim 依据及确切对象绑定，角色隔离由 OpenFlow 管理；apply、索引与查询不把上游复核通过证明作为运行门禁，不要求代码复核者公钥或密码学签名，也不认证 Agent 身份或知识语义。纯文档不设真人确认门；共享发布回执仍按其自身规则验证，跨机查询还须核对实际文件内容绑定。新模块映射按项目相对路径、配置指纹和文件哈希核验；可选版本标签须有出处，不能据标签推断未提供的身份或状态。旧证据的显式 Git 恢复保留兼容。

Skill 可人工逐个调用，只校验本职业务数据和固定检查；OpenFlow 负责流程顺序、角色隔离及交棒合法性。节点不要求 Workflow 身份、catalog 登记或上游通过凭证。
