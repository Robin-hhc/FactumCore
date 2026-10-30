# WiFi 知识治理巡检 Workflow

用于个人本地或外部周期调度，发现未入库 raw、直接登记代码变更和旧欠账。自有治理节点按 L1—L4 编号，各加载一个窄 Skill；中间复用的入库节点保持 P1—P6；P4由 `hs-knowledge-review` 独立审阅。

命令表以 Windows 为例，在实际知识根执行；POSIX 将 `.\knowledge.cmd` 换成 `sh ./knowledge.sh`。已注册入口时也可用 `knowledge`。

| 节点 | Skill | 命令 |
|---|---|---|
| L1 `sync_workspace` | hs-knowledge-patrol-sync | .\knowledge.cmd patrol sync |
| L2 `plan_patrol` | hs-knowledge-patrol-plan | .\knowledge.cmd patrol plan |
| L3 `refresh_index` | hs-knowledge-patrol-reindex | .\knowledge.cmd patrol reindex |
| L4 `complete_patrol` | hs-knowledge-patrol-complete | .\knowledge.cmd patrol complete |

首节点从已有上下文或当前工作区的 `AGENTS.md`、`config.yml` 确定知识根和执行端，不明确时先询问用户。同步仅执行控制端明确配置的请求；无配置检查本地，失败不继续。计划须新起CLI加载同步后的实现、配置和规则，取得实际 `plan_ref/source_request`、统计与缺口。

`needs_ingest` 将完整材料请求交 P1 的 `source prepare`，保留新增 raw 与待修卡来源并集；纯代码允许空 raw。之后复用 ingest 的 P2—P6及返工边，不嵌套Workflow。`needs_index` 只修派生索引；`unchanged` 仍需完成核验。maintain Skill 只处理独立引用审计和来源限制维护。

完成核验采用原计划及实际发布／完成引用，真实 `completed` 才报告成功基线推进；欠账、失败、漂移或P6／清理未完保持 `pending`。`pending`／`blocked` 都结束本轮并保留原因及确切续办请求；续办交明确修复任务，已发布内容只续办原批次。

固定观察 `logs/patrol/` 与本机状态 `.build/runtime/patrol-state.json` 不手改、不由P6清理，也不上库。代码 current／guidance／historical 按实际用途处理，不改写旧定位或猜替代入口。

运行实现随知识根分发，Skill仅提供指引。内部Git-MM同步argv为 `["git","mm","sync","-j8"]`，cwd由执行端用 `git mm --root-dir` 运行时解析，不写死机器路径；其它MM子命令不作假设。周期触发、SSH与reviewer隔离由宿主配置，公司环境与业务效果单列验收。

详细流程见领域[详细设计 §3.1](../../../../himate/himate-knowledge-wifi-mp/docs-llm-wiki/知识库详细设计.md#31-lint-的检查流程)。升级已有Workflow副本时核对四个治理Skill、P4 review和P5 record绑定。
