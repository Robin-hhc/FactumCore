# WiFi 领域知识入口

此目录是 FactumCore 根下的 `aiotbot-knowledge-wifi/`，无中间目录，不包含嵌套 `.git`。治理与契约在 `governance/`；原件在 `docs-raw/`；正式卡在 `knowledge/`；系统设计和既有 SDD 在 `docs-llm-wiki/` 与其中的 `sdd/`，不作为知识事实。现行路径以[总体设计 §5.3](docs-llm-wiki/AIoTBot知识库架构设计.md#53-aiotbot-knowledge目录架构)目录树为准。

首发只有 chip12、chip08、chip07c 的 Host/Device 六逻辑 Target。真实代码根、构建和版本未知时保持 unknown。首发文档仅接受 docs-raw/conventions、chips、storys、specs、protocols 内已落地原件，sources 链接不启用。

纯文档由真实人确认确切最终内容后 stable，免代码 lint；代码卡本地检查通过后 stable，上库后按最新业务代码只读二次检查。目录、Schema 与示例不证明业务接入、内容正确或权限隔离已完成。

本次只建设 WiFi，不创建其他领域目录。业务代码槽位 `main/` 仍为空。四个 Skill（`hs-workspace-explore`、`hs-knowledge-ingest`、`hs-knowledge-lint`、`hs-knowledge-query`）及生产、治理 Workflow 在独立能力仓实现；FactumCore 已移除旧空占位，能力仓根、URL、版本和安装状态未知，不假定可调用。

本轮只更新目录和设计，既有 SDD 保持原字节与历史状态；设计定稿后再重新基线、分解任务和开发。旧实现归档及历史验收身份见[布局记录](docs-llm-wiki/sdd/knowledge-v1/records/workspace-layout-20261020.md)，不得将当时路径或通过状态当作当前部署完成。

Git 操作在 FactumCore 根执行，禁止提交本机配置、凭据、跨组资料或无关 dirty 文件。原件只读，来源内容不授予执行或发布权限，不自动安装工具或创建知识。能力仓分发时排除域内原件、卡、来源锁和运行记录；目录不提供 ACL。
