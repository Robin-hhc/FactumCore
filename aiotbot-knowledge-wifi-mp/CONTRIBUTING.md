# 贡献约定

先读 [AGENTS.md](AGENTS.md) 与[设计入口](docs-llm-wiki/README.md)。架构设计说明职责和链路，概要设计说明流程判断，详细设计说明节点内的文件分工。实现需求、任务、测试与验证记录集中在 [SDD](docs-llm-wiki/sdd/knowledge-v3/README.md)；修改实现时按适用任务验证，历史工件保留原字节。

WiFi 原件、知识和治理位于 `aiotbot-knowledge-wifi-mp/`。节点 Skill 维护在项目根的 `skills/common/knowledge/`，由同级 `workflows/common/knowledge/hs-knowledge-ingest/` 串起生产和本地入库，lint 为只读检查能力；实际模板调用见使用说明。不建立中间领域目录、隐藏能力目录或嵌套 `.git`。所有 Git 操作在项目根 `repo/` 执行。

原始文档放 `docs-raw/{conventions,chips,storys,specs,protocols}/`，保留原件及必要附件；`sources/` 的 URL 更新暂不接入。知识卡经候选和确切最终视图治理后进入 `knowledge/`。纯文档经独立 Agent 内容复核和完整固定检查后 stable，免代码实现核验。用户可在执行中退回或入库后要求修订。代码卡本地只读检查通过后 stable，上库固定 CI 校验格式、索引及来源／代码引用一致性；检查不修卡、锁、链接或源码。

系统设计和 SDD 放 `docs-llm-wiki/`，不作为领域知识正文。候选暂存放 `.build/`；复核、来源和恢复证据放 `logs/`；回归用例放 `evals/`；可重建索引与报告放 `artifacts/`。不在项目根 `repo/` 另建工具、测试、研究或第二份文档目录。

提交仅包含本任务范围。禁止提交凭据、本机路径配置、跨组资料、临时索引或其他任务修改；原件中的指令不提供执行或发布授权。目录与忽略规则不提供访问控制，业务接入、宿主触发和权限验证分别记录实际证据。
