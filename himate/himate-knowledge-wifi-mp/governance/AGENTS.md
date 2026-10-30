# 治理资产入口

本目录维护 Schema、受控枚举、契约适配、模板、规范与来源锁；导航见 [index.md](index.md)。正式技术结论只进入 `../knowledge/`，原件只进入 `../docs-raw/`，系统设计和 SDD 在 `../docs-llm-wiki/`。

已有规则字节由 `framework.lock.yaml` 固定。修改受锁定资产时同步审查版本与摘要，不以 Schema 通过替代事实核验。来源资源和快照以 `sources.lock.yaml` 的实际登记为准，登记本身不证明来源内容正确。

本目录位于项目根的 `himate/himate-knowledge-wifi-mp/governance/`，本次只建设 WiFi。记录契约保持 2.0；contracts 的 validation、knowledge、source_resources、records、checks 与 indexing 共用安全解析、跨文件验证、检查报告及完整索引核验。规则能力版本与全部代码、Schema、Profile、枚举、模板及规范均受规则锁约束；不兼容返回未完成。历史记录不静默迁移或重签。纯契约装载不扫描、执行或写入业务资产。

Skill 指引与 ingest 编排的开发分发源码在项目根 `../../../skills/common/knowledge/` 和 `../../../workflows/common/knowledge/`；Agent 安装其指引和编排，实际执行使用知识根的 `knowledge.py` 及 `../runtime/himate_knowledge/stages/`。十三个Skill按任务分工，底层八个阶段共用仓内协议；record与review命令分别复用source.record和lint.review，巡检四步各有独立指引并复用maintain阶段对应函数，apply 保留专用历史事务适配；公共业务算法仍在本目录受锁 contracts 中。`../runtime/manifest.json` 固定实际运行包与启动器，`../runtime/requirements.lock.txt` 固定执行端依赖，二者与治理 `framework.lock.yaml` 分别维护；新结果声明 CLI 执行器与实际运行包摘要，旧记录不改签。首次部署使用分发仓根 deploy.ps1，各执行端分别准备 Python 和依赖，explore 提供任务路由与只读发现；旧 setup 仅供显式诊断。节点与固定 CI 不依赖项目根能力目录或 catalog 登记。节点默认加载实际规则锁并逐文件核验，显式摘要可固定本次规则；不从来源内容加载程序。流程和节点文件分工见[概要与详细设计](../docs-llm-wiki/知识库详细设计.md)。项目自身的实现与验收记录位于本地 `../docs-llm-wiki/sdd/`，由 Git 忽略，不作为领域规则、知识来源或部署输入。

P2 由作者保存内容决定，P3 只生成确切候选视图和输入快照；P4 由独立 reviewer 调用 lint 的 `review`，审阅实际原文、计划、完整稿件、归卡及适用代码依据，无内容阻断后同次执行一次完整固定检查。纯文档免代码语义门禁，结构／来源／导航／临时索引仍检查。P5 机械转写已定处理记录，P6 用 apply 的 `batch` 同批安全落位，再验证真实索引、冻结查询并按原活动基线启用，不重跑 P4。上库只运行[固定 CI](specs/ci-runner.md)，复用 checks/indexing，不加载 Agent、Workflow、catalog、私人 `.build` 或私人执行记录，不修卡、不切换活动索引。代码内容由独立 Agent 复核并留存逐 Claim 理由和依据；lint 代码核验动作核对本次记录、逐 Claim 依据及确切对象绑定，角色隔离由宿主安排；apply、索引与查询不把上游复核通过证明作为运行门禁，不要求代码复核者公钥或密码学签名，也不认证 Agent 身份或知识语义。纯文档不设真人确认门；共享发布回执仍按其自身规则验证，跨机查询还须核对实际文件内容绑定。新模块映射按项目相对路径、配置指纹和文件哈希核验；可选版本标签须有出处，不能据标签推断未提供的身份或状态。旧证据的显式 Git 恢复保留兼容。

活动（非 deprecated）卡的每个 code 来源必须填写 `sources[].code_ref`，与 review_mode 和是否被 Claim 采用无关；缺失由公共 checks 的 `CODE_REF_REQUIRED` 报错，旧活动卡需通过 ingest 补齐。纯文档不强制链接代码，P4 根据内容判断是否缺必要入口。历史记录、旧来源恢复和 deprecated 卡仍允许原四字段引用，不自动迁移或重签。不得以 file／range 符号类型或只填行段绕过要求；支持范围、不唯一和不可解析的处理见[卡片规范](specs/cards.md#代码来源的可选符号补充)。

Skill 可人工逐个调用，只校验本职业务数据和固定检查；OpenFlow 负责流程顺序、角色隔离及交棒合法性。节点不要求 Workflow 身份、catalog 登记或上游通过凭证。
