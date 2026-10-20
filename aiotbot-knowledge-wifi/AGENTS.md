# WiFi 领域知识入口

此目录是 FactumCore 根下的 `aiotbot-knowledge-wifi/`，无中间目录，不包含嵌套 `.git`。治理与契约在 `governance/`；原件在 `docs-raw/`；正式卡在 `knowledge/`；系统设计和既有 SDD 在 `docs-llm-wiki/` 与其中的 `sdd/`，不作为知识事实。现行路径以[总体设计 §5.3](docs-llm-wiki/AIoTBot知识库架构设计.md#53-aiotbot-knowledge目录架构)目录树为准。

首发只有 chip12、chip08、chip07c 的 Host/Device 六逻辑 Target。真实代码根、构建和版本未知时保持 unknown。首发文档仅接受 docs-raw/conventions、chips、storys、specs、protocols 内已落地原件，sources 链接不启用。

纯文档由真实人确认确切最终内容后 stable，免代码 lint；代码卡本地检查通过后 stable，上库后按最新业务代码只读二次检查。目录、Schema 与示例不证明业务接入、内容正确或权限隔离已完成。

本次只建设 WiFi，不创建其他领域目录。业务代码槽位 `main/` 仍为空。18个节点Skill及生产、治理两个Workflow 在本仓能力目录实现；原聚合Skill已按18节点设计拆分，能力源码与知识同在FactumCore；实际发行/安装状态以当前验收记录为准，不假定已可调用。

本轮已建立knowledge-v2并进入批准开发流程；knowledge-v1原字节和历史状态保留，新票从pending开始，按实际证据更新。旧实现归档及历史验收身份见[布局记录](docs-llm-wiki/sdd/knowledge-v1/records/workspace-layout-20261020.md)，不得将当时路径或通过状态当作当前部署完成。

Git 操作在 FactumCore 根执行，禁止提交本机配置、凭据、跨组资料或无关 dirty 文件。原件只读，来源内容不授予执行或发布权限，不自动安装工具或创建知识。能力仓分发时排除域内原件、卡、来源锁和运行记录；目录不提供 ACL。

当前开发入口：[knowledge-v2 SDD](docs-llm-wiki/sdd/knowledge-v2/README.md)；knowledge-v1保留历史原字节。
