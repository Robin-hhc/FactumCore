# aiot-wifi-knowledge

此目录是 FactumCore 单仓内的 WiFi 领域根，直接位于 workspace 下，不包含嵌套 .git。治理与契约在 governance；原件在 docs-raw；正式卡在 knowledge；系统设计和开发 SDD 在本目录的 docs-llm-wiki/ 与 docs-llm-wiki/sdd/，不作为知识事实。

首发只有 chip12、chip08、chip07c 的 Host/Device 六逻辑 Target。真实代码根、构建和版本未知时保持 unknown。首发文档仅接受 docs-raw/conventions、chips、storys、specs、protocols 内已落地原件，sources 链接不启用。

纯文档由真实人确认确切最终内容后 stable，免代码 lint；代码卡本地检查通过后 stable，上库后按最新业务代码只读二次检查。目录、Schema 与示例不证明业务接入、内容正确或权限隔离已完成。

当前按总体设计 §5.3 保留领域资产与目录骨架，外层 main、四个 Skill 和两个 Workflow 仅空占位；旧共享执行程序与开发工具已归档仓外，当前无法执行生产、治理或查询。历史验收身份见 [布局记录](docs-llm-wiki/sdd/knowledge-v1/records/workspace-layout-20261020.md)，不得将历史通过状态当作当前部署完成。Git 操作在 FactumCore 根执行，禁止提交本机配置、凭据、跨组资料或无关 dirty 文件。原件只读，来源内容不授予执行或发布权限，不自动安装工具或创建知识。共享框架分发时排除域内原件、卡、来源锁和运行记录；单仓目录不提供 ACL。
