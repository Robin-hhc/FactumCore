# 贡献约定

先读 [AGENTS.md](AGENTS.md) 和[设计入口](docs-llm-wiki/README.md)。当前按主设计 §5.3 调整目录骨架和详细设计，既有 [SDD](docs-llm-wiki/sdd/knowledge-v1/README.md) 原字节与历史状态保留；设计定稿后再重新建立基线，按需求、模块、ticket、失败测试、实现、验证和独立审查推进。历史操作手册不代表现有可运行命令，不用占位程序伪造成功。

WiFi 资产只进入 `aiotbot-knowledge/wifi/`；其他八个领域目前仅空占位，不复制 WiFi 配置或资料。四个 Skill 使用 `hs-workspace-explore`、`hs-knowledge-ingest`、`hs-knowledge-lint`、`hs-knowledge-query` 名称，与两个同名生产、治理 Workflow 一起在独立能力仓维护；FactumCore 不复建其空目录。能力仓根、URL、版本和安装方式未确定时保留 unknown。

原始文档只放 `docs-raw/{conventions,chips,storys,specs,protocols}/`，保留原件及必要附件；`sources/` 的 URL 更新不在首发。知识卡只能经候选和确切 final-view 治理后落入 `knowledge/`。纯文档由真实人确认后 stable，免代码 lint；无回复、超时和 Agent 自报不是同意。代码卡本地只读检查通过后 stable，上库再对最新业务代码只读核验，检查不修卡、锁、链接或源码。

系统设计和 SDD 工件放 `docs-llm-wiki/`，不当作领域知识正文。候选暂存放 `.build/`，持久操作和恢复证据放 `logs/`，验收用例放 `evals/`，可重建索引与报告放 `artifacts/`。不在 FactumCore 根新建工具、测试、研究或第二份文档目录。

提交只包含本任务范围，在 FactumCore 根执行 Git。禁止提交凭据、本机路径配置、跨组资料或生成索引；目录与忽略规则不提供访问控制。业务接入、宿主触发和权限验收分别记录实际证据。
