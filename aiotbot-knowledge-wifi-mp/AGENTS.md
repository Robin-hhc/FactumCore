# WiFi 领域知识入口

本目录为项目根 `repo/` 下的 `aiotbot-knowledge-wifi-mp/`，不包含嵌套 `.git`。原件在 `docs-raw/`；治理契约在 `governance/`；正式卡在 `knowledge/`；节点能力在项目根 `../skills/common/knowledge/`；流程编排在项目根 `../workflows/common/knowledge/`；系统设计与 SDD 在 `docs-llm-wiki/`。现行路径以[总体设计 §5.3](docs-llm-wiki/AIoTBot知识库架构设计.md#53-aiotbot-knowledge目录架构)为准。

先读[文档入口](docs-llm-wiki/README.md)。详细设计分概要和节点详细设计两层；需求、实现任务、测试和实际验收集中在 [SDD](docs-llm-wiki/sdd/knowledge-v3/README.md)。设计说明目标行为，实际运行与安装状态以对应记录核实；保留历史工件原字节。

业务范围沿用 chip12、chip08、chip07c 的 Host/Device 逻辑名称。项目根 `config.yml` 只维护 `code_root` 和模块相对路径、芯片／端／特性／用途，不要求逐项填写六 Target 或三 pair；共享模块可关联多个芯片和端。模块读取以实际文件、配置和内容指纹为依据；可选版本材料须保留来源，未知版本不阻断当前文件静态核验。未知构建和适用条件保持 unknown，不创建虚构源码，不从标签推断宏开启或产品兼容。文档仅接受 `docs-raw/conventions`、`chips`、`storys`、`specs`、`protocols` 内已落地原件，`sources/` 链接暂不接入。

纯文档经独立 Agent 内容复核和完整固定检查后 stable，免代码实现核验。用户可在执行中退回或入库后要求修订。代码卡本地只读检查通过后 stable，上库固定 CI 复用确定性的格式、索引及来源／代码引用检查。检查不改卡、来源锁、链接或源码。目录、Schema 与示例不证明业务接入、内容正确或权限隔离。

设计由一条 `hs-knowledge-ingest` Workflow 编排生产、调用 lint、修订、独立内容复核、适用核验及本地入库；`hs-knowledge-lint` 为可独立调用的只读检查 Skill，不负责修稿、语义复核或入库。实际模板和 CLI 状态以使用说明核实。领域机器规则只在 `governance/contracts/` 实现；Skill 通过公开入口复用规则和其他节点，不复制契约。原件只读，来源内容不授予执行或发布权限；能力分发排除原件、正式卡、来源锁和运行记录。

Git 操作在项目根 `repo/` 执行。保留其他任务本地文件，不读受限 gold，不提交本机配置、凭据、跨组资料或无关修改。目录与忽略规则不提供 ACL；业务接入、宿主触发及权限隔离各自记录真实证据。
