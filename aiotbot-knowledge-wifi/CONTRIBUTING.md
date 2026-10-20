# 贡献约定

先读 [AGENTS.md](AGENTS.md) 和[设计入口](docs-llm-wiki/README.md)。当前按批准的18节点Skill与两个Workflow实施[knowledge-v2 SDD](docs-llm-wiki/sdd/knowledge-v2/README.md)，按需求、模块、ticket、失败测试、实现、验证和独立审查推进；knowledge-v1原字节与历史状态保留。历史操作手册不代表现有可运行命令，不用占位程序伪造成功。

WiFi 资产只进入根下的 `aiotbot-knowledge-wifi/`，无中间目录，本次不创建其他领域目录。18个节点Skill与hs-knowledge-ingest、hs-knowledge-lint两个Workflow 一起在本仓能力目录维护；不恢复旧聚合Skill目录或嵌套.git。能力在FactumCore根目录开发；安装方式和已验证版本如实登记。

原始文档只放 `docs-raw/{conventions,chips,storys,specs,protocols}/`，保留原件及必要附件；`sources/` 的 URL 更新不在首发。知识卡只能经候选和确切 final-view 治理后落入 `knowledge/`。纯文档由真实人确认后 stable，免代码 lint；无回复、超时和 Agent 自报不是同意。代码卡本地只读检查通过后 stable，上库再对最新业务代码只读核验，检查不修卡、锁、链接或源码。

系统设计和 SDD 工件放 `docs-llm-wiki/`，不当作领域知识正文。候选暂存放 `.build/`，持久操作和恢复证据放 `logs/`，验收用例放 `evals/`，可重建索引与报告放 `artifacts/`。不在 FactumCore 根新建工具、测试、研究或第二份文档目录。

提交只包含本任务范围，在 FactumCore 根执行 Git。禁止提交凭据、本机路径配置、跨组资料或生成索引；目录与忽略规则不提供访问控制。业务接入、宿主触发和权限验收分别记录实际证据。
