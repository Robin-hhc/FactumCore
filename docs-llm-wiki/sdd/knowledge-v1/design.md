# 首发 SDD 模块设计

## 1. 交付根、分层和接口

当前开发 workspace 是 FactumCore 仓根。按用户部署决议，框架、SDD 与 WiFi 领域资产统一在一个 Git 仓维护；SDD 真源为 `docs-llm-wiki/sdd/knowledge-v1/`，`aiot-wifi-knowledge/` 为直接子目录，不含嵌套 .git。既有 `E:\FactumCore\aiot-knowledge/` 保持原身份，不搬迁或覆盖。下面 `W` 表示 FactumCore 根，`S=W/skills/common/knowledge/_shared`，`K=W/aiot-wifi-knowledge`。历史隔离开发目录仅作已记录验证的来源，不再是发布根。所有目标路径的存在与完成状态分别验收。

固定边界：首发文档只取 `K/docs-raw/{conventions,chips,storys,specs,protocols}/` 的实际原件；排除控制文件、sources、URL、仓外映射及越界联接。manual_document 只需真实人工确认，不跑代码本地/合入门禁；代码本地通过即 stable、可供 local 消费，上库再按最新源码只读核验。六 Target/三 pair 先建逻辑登记，真实映射、宿主触发、ACL 分别验收。

| 模块 | 主责与拥有文件 | 对外接口与交换对象 | 依赖及写入边界 |
|---|---|---|---|
| M01 契约与运行基础 | `S/__init__.py,cli.py,contracts.py,scope.py,receipts.py`；`K/governance/{schemas,contracts,templates,specs}/`；薄 check 包装 | `ContractBundle`、`Diagnostic`、`ResultEnvelope`；校验 config/card/source/record；`match_scope(Claim, QueryContext, EvidenceState)` 返回逐断言资格和原因 | 根模块。配置是 Target/pair 路由唯一真源，registries 只存公共枚举；纯解析不代表事实核验。导入、校验与诊断不写业务资产 |
| M02 项目发现绑定 | `S/workspace.py`；workspace 配置、用户级 registry/托管薄规则；explore reference | `resolve_project(path, base, registry, authority) -> ResolvedBinding`；`load_context(binding, reader) -> ProjectContextReceipt` | 依赖 M01。resolved 与 context_loaded 分开；后者带实际入口字节摘要/读取轨迹，输出实际内容供宿主加载。只写获准缓存/回执，不扫描整盘、不启动摄入 |
| M03 来源快照 | `S/sources.py`；`K/governance/sources.lock.yaml`；`K/logs/evidence/`；raw 导航/规范 | `capture_document`、`capture_code`、`resolve_source` 返回 `SourceResource/SourceSnapshot`、恢复对象与 locator；register 返回待应用锁增量 | 依赖 M01 和显式配置身份，编排时接 M02 绑定。原件/源码只读；锁增量进入 final-view；持久包按对象摘要寻址，extract 文本不是新原件入口 |
| M04 卡片与六决策 | `S/cards.py,changes.py` 的 plan/materialize；七类模板/正文导航；关系 Contract | `parse_card`、`plan_ingest`、`materialize` 返回 `Card/Claim`、六决策计划、`ChangeSet`、最终 stable 字节与 review-package | 依赖 M01/M03。只写 `.build/<operation_id>/`；no_change/defer 正常结束。业务语义来自证据和有说明的生产活动，不把字段解析当正确性证明 |
| M05 人工确认与事务 | `S/changes.py` 的 confirm/apply/recover；人工模板、journal、operations/document-reviews 日志 | `confirm_document(final_view, human_action)` 返回 `ManualReviewRecord`；`apply(changeset, proof, baseline)` 返回事务结果；`recover(operation)` 按 journal 续做/恢复 | 依赖 M04；代码证明由 M06 提供。确认绑定最终字节/来源/scope；锁+CAS+全域 ID/关系技术视图；只改明确清单，保留其他工作 |
| M06 代码双门禁 | `S/checks.py`、`K/check.py,check.sh`；local/merge references；证明日志 | `check_local(final_view, context, verifier)` -> `LocalCheckRecord`；`check_merge(H,B,T,V, trusted_policy)` -> `MergeGateRecord`/逐 ClaimResult | 依赖 M01/M03/M04。只读检查，缺实证 incomplete；semantics/runtime 等义务需要真实方法和证据，未执行不得 pass。CI 独立输出、不 apply、不更新待审卡/锁/链接/业务代码 |
| M07 代次索引与消费 | `S/index.py,search.py`；索引 manifest/bodies/active；SearchReceipt | `build_index(channel, frozen_input)` -> 未激活 generation；`activate(expected_active,new)` 条件切换；`search(context)` -> 固定代次候选；`read(generation,card)` -> 同代正文 | 依赖 M01/M05/M06 各 review_mode 的记录；叠加 M08 当前状态。先断言资格过滤再 top-k，local/shared 分开；不写正文、不自动建卡 |
| M08 持续治理 | `S/maintenance.py`；events/watermarks；运维规范 | `impact(event, graph)` -> 持久影响/阻断；`reconcile(event, matching_proof, channel)` -> 分渠道恢复；`current_state()` 提供有效性 epoch | 依赖 M01/M03/M04，恢复依赖 M05/M06/M07。source/requires/derived_from 条件化传播，related_to 不全量传播；先阻断再推进扫描水位，修卡/证明/激活齐备再推进应用水位 |
| M09 Skills/Workflow 与部署验收 | 四个 hs-common Skill、两个 Workflow、merge-stage；入口说明、使用/维护、evals | 生产 P1–P5、治理 G1–G9、消费 C1–C7 阶段日志/交接摘要；安装适配与 acceptance runner | 编排 M01–M08，不复制引擎。用户级可见 Skill+薄规则提高触发稳定性，不保证每个宿主必触发；部署与外部授权由真实环境验证 |

接口共同规则：各命令显式接收领域根与操作/请求身份，不依赖 cwd；输出 `schema_version,status,operation_id/request_id,input_digests,output_refs,diagnostics,retryability`。status 至少区分 success/no_change/deferred/incomplete/conflict/waiting/error，退出码在 M01 固定。所有 digest 对规范化载荷计算，manifest/记录不把自身摘要放进载荷集合；实际 commit 通过外部关联记录绑定。禁止远端 Schema `$ref`、提交方自选任意执行插件、自动安装和材料内命令执行。


## 具体接口与实施门槛

上表是完整首发的逻辑接口与职责边界，不表示程序已存在。T01/T02 的具体函数、CLI 和退出码由 [first-slice](first-slice.md) 固定；后续接口在对应 ticket 的测试前细化，变更影响记入验证记录。Schema 只声明形状，后续 Contract/Agent/运行义务不能由基础解析替代。

模块各自的 spec/design/tasks 见 modules/，全局需求不在模块文件复制成第二套规则；每个文件的原始职责、开发要求和验收可从 traceability.json 恢复并核对固定设计摘要。

当前框架与 WiFi 领域统一由 FactumCore Git 管理；.gitignore 不排除 aiot-wifi-knowledge 正式资产，只忽略暂存、可重建产物和本机配置。框架 SDD 留在 docs-llm-wiki/sdd，领域事实留在 K；未来公共框架发行须显式排除组内原件、卡、锁、日志和索引，单仓不提供 ACL。远端为用户指定的 Robin-hhc/FactumCore；实际合入与推送分别记录，不以配置远端替代发布验收。全局安装和真实业务接入仍未验收。
