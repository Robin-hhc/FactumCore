# 贡献约定

先读 [AGENTS.md](AGENTS.md) 和[当前 SDD](docs-llm-wiki/sdd/knowledge-v1/README.md)，按需求、模块、ticket、失败测试、实现、验证和独立审查推进。当前是目录骨架，未恢复受信执行程序前不运行历史操作手册中的命令，不用占位程序伪造成功。

原始文档只放 `docs-raw/{conventions,chips,storys,specs,protocols}/`，保留原件及必要附件；`sources/` 的 URL 更新不在首发。知识卡只能经候选和确切 final-view 治理后落入 `knowledge/`。纯文档需真实人工确认；代码卡需本地检查，上库再对最新业务代码只读核验。

系统设计和 SDD 工件放 `docs-llm-wiki/`，不当作领域知识正文。候选暂存放 `.build/`，持久操作和恢复证据放 `logs/`，验收用例放 `evals/`，可重建索引与报告放 `artifacts/`。不在 FactumCore 根新建工具、测试、研究或第二份文档目录。

提交只包含本任务范围，在 FactumCore 根执行 Git。禁止提交凭据、本机路径配置、跨组资料或生成索引；目录与忽略规则不提供访问控制。业务接入、宿主触发和权限验收分别记录实际证据。
