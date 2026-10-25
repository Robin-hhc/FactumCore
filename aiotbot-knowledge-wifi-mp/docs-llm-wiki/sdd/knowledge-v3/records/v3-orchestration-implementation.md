# v3 入口、编排与原件处理实施记录

对应只读审计 `v3-audit-orchestration.md` 的 O1–O7；批准详细设计与 v1/v2 历史工件未修改。此记录只描述本次实现与实际测试。

## 已实施

- 新增 `hs-knowledge-source-scan`：公开 `scan / prepare / record / status`。无 source 参数默认五类 raw；局部扫描不推断范围外删除；历史按逐路径前驱解释；同hash未完成及代码上下文受限事项继续处理。
- P1 只读调用 `maintain inspect-context`；P2 从 source/Claim、全状态主题候选以及 requires/derived_from 依赖重建阅读候选；普通 related_to 不扩散。逐卡保存实际旧原版的不可变批内副本、完整恢复描述、定位和差异。
- P6 对账后只生成 `.build/operations/<op>/ingest-record.yaml`，嵌入可移机解释的固定扫描清单；正式路径随 P7 同批落位。记录批不夹带失败稿件，不伪造 lint 或确认。
- 活动编排改为唯一 ingest Workflow，E0 不在其中。补独立 P3/P4 内容复核、P4固定预检、P5只读lint、P6记录、P7事务／索引／目标查询／精确提交验证；移除旧 lint 活动模板。保留既有 OpenFlow 格式与 loader。
- installer 安装20个Skill与1个Workflow，并输出 ingest/lint/query/status/index rebuild/recover 的逻辑分派表；status指 source-scan公开只读动作。复制完成仍不代表宿主已经注册或触发命令。
- `validate_design`、节点 artifact scopes 与入口测试同步新图；旧委托 Agent merge wrapper 测试由治理负责人的固定 CI 测试替代，不动历史 SDD。
- 来源恢复共用 `recover_snapshot`，支持配置选定仓库中的确切 Git commit/blob。capture自动识别与已提交raw blob相同的当前字节，无需额外参数；否则保留local证据并交P7报告portable缺口。原版可在没有第一台机器缓存时恢复／重抽取，冻结text与locator摘要须仍相同。Git读取禁网络协议、lazy fetch、hooks、交互，限制30秒；不接受来源自报repo_root。

## RED → GREEN 证据

| 切片 | 最初 RED | 结果 |
|---|---|---|
| 默认扫描 | source-scan CLI不存在、未返回结果 | 公开CLI能无source枚举两类合成原件并排除sources链接 |
| P2材料 | prepare公开动作缺实现 | 不同状态两卡各自旧snapshot恢复与文字检查通过 |
| P6记录 | record公开动作缺实现 | defer记录离机可解释，后续同hash仍unfinished |
| status | UNKNOWN_ACTION | 仅读保存事实，不新增知识或推进操作 |
| 单Workflow | 入口仍bind_project | scan入口、唯一Workflow、最终lint与记录顺序通过 |
| 安装逻辑入口 | catalog无commands | 20包/单模板与命令分派表通过 |
| Git原件恢复 | 将workspace路径错误当local evidence导致UNSAFE_PATH | 仅Git原版仍恢复确切旧字节、当前字节不同能区分 |
| 自动Git捕获 | recovery仍evidence_object | 自动登记匹配HEAD的commit/path；移除第一机缓存后精确重构通过 |

## 截止冻结窗口的实际回归

- E0现有公开CLI：5 passed。
- installer：15 passed、1 skipped（需平台／外部条件的既有项）。
- Workflow验证测试：4 passed、1 skipped（未配置实际OpenFlow源码路径）；真实树validator曾只报新lint缺包内tests与dev锁，已交治理负责人补齐。
- source-scan：9 passed（27.94秒），包含局部扫描历史不丢失、范围外删除不推断、记录覆盖／实质skip缺复核拒绝、显式依赖与普通related隔离、外部scope拒绝。随后新增第10个测试揭示pending formal记录错误推进完成，见下。
- source-capture：35 passed、1 failed（45.95秒）。唯一失败是拒绝原件篡改的公开错误码兼容问题：共用resolver返回EVIDENCE_OBJECT_CHANGED，而既有合同要求SOURCE_INTEGRITY_ERROR；仍正确拒绝篡改，需边界映射回原码。
- confirmation-prepare：3 passed。
- public_qualification：2 passed（54.88秒）。此次未复现先前并行修改期的source display response identity失配，也未复现追加无关来源导致老引用失效。

## 冻结窗口期间发现并交统一修复

1. 新反例 `test_pending_formal_record_does_not_prove_completed_processing`：pending记录即便放进formal路径，也不能凭unit.progress=skipped推进完成。当前RED为unchanged，应为unfinished；需同时核P7实际记录落位事实（content: applied；record-only: recorded）。为避免跨包摘要漂移，已告root，等待统一修复窗口。
2. capture错误码兼容项如上，等待统一窗口映射。
3. `plan_v3.content_review` 用previous_progress识别P1免审，但扫描字段为progress；mixed批P1扫描跳过应免重复语义复核，已交content负责人。
4. 纯代码Claim由inspect-context标affected、raw清单为空时，P3要求非空raw unit_ids会卡住；content负责人将增加绑定current_context的maintenance_units，不伪造raw项，Workflow需同步提示。

没有断言真实宿主触发、真人确认、真实六Target、CI服务器合入或权限隔离已经验收；结构loader、固定脚本与合成输入分别报告。

## 统一修复窗口

- pending formal反例与capture公开错误码已修，相关2个目标测试GREEN；record-only须有实际recorded落位事实，内容批须实际applied，不能凭单元自报进度跳过。
- importlib模式测试不再依赖模糊的 `from conftest import ...`；本地测试hashhelper或显式唯一模块加载替代。自动Git捕获测试在importlib模式GREEN。
- 原生上游loader实测RED定位为复用Skill的合同把不同节点exit做union；使用其既有多YAML合同+applies_to原生能力修复。source-scan、change-plan、publish各节点分别约束自己的产物，不更换／修改上游validator。
- 现在是20 Skills、24 native artifact contracts、1 Workflow。真实OpenFlow固定源码 `1901a463efca222542a4634d7ce50c7b244b2bab` 的11个loader文件hash校验后，5个Workflow测试全部通过，包含真实loader；installer增加附加合同校验反例RED→GREEN，16 passed、1 skipped。
- 已从真实当前源码隔离安装到 `C:/Users/Robin/AppData/Local/Temp/factum-v3-orch-capabilities-20261025-1`，随后真实上游loader返回 static_valid、`workflow_ids=[hs-knowledge-ingest]`、skill_count=20、contract_count=24。此项证明真实源码安装／加载，仍不证明宿主触发或真实角色权限。
- P2新增显式 `code_bundle_refs`，公开CLI反例RED（combined无代码材料）→GREEN：调用既有公开capture resolver核对确切code bundle及当前授权身份，把新代码不可变字节与逐卡旧材料同时交P3。raw清单仍为空，不伪造raw文件；历史或无法授权的代码不能冒充当前材料。
- P6把绑定语义计划中的maintenance_units复制为共享maintenance_dispositions，保留无raw时defer/failed/uncovered欠账；公开CLI RED→GREEN。Workflow同时补M-only输入、当前代码材料和P7相同check_inputs要求。
- 修复后 source-scan 全组12 passed（importlib模式，36.81秒）；另同一当前代码材料测试追加真实代码字节变化后拒绝旧bundle为当前材料的分支，1 passed（6.85秒，exit3/CURRENT_CODE_REQUIRED）。所有已报告的我侧实现缺陷均已修复；整仓最终回归由root统一执行。
- 最后交叉复核补混合视图显式出口和共享记录对象progress兼容，两项均有公开RED→GREEN；最终source-scan 13 passed（42.50秒）、Workflow含真实OpenFlow loader 6 passed（17.32秒），相关ruff通过。完整交叉复核及CI空库坏来源锁反例见SDDv3 `records/review-orchestration.md`。
- 代码来源恢复接点追加：真正committed授权代码自动登记Git recovery并strict重验；dirty/export仍local；跨机无`.c`本机抽取缓存能按冻结规则重建，未知extractor保持未完成；历史本机fallback与P7严格portable选项分开。source-capture全包37 passed（45.67秒）。P7 strict选项／同ID存储说明迁移由content负责人提供公开目标验证。记录批关联既有卡的P6正反例已补，等待治理formal+overlay及重建限制API统一落地后复测。
- 最终治理APIready后，P6受控空view验证既有正式卡关联并拒绝虚构卡／Claim和build稿件引用；source-scan整包17 passed（54.10秒，冻结包/importlib）。期间一次maintain并行变更触发PACKAGE_CHANGED，单例重放与随后整包已通过。所有我侧生产、引用说明和Workflow再次冻结；代码capture子operation约定已同步，未换引擎、未改批准设计。
