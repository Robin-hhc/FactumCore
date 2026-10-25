# v3 实现审计：入口、编排、原件扫描与处理记录

审计日期：2026-10-25。只读审计，未修改生产实现，未读取真实 raw、知识卡正文或受限 gold。设计依据为 `docs-llm-wiki/sdd/knowledge-v3/baseline/知识库详细设计.md`，SHA-256 `32df6c9505f3f7c6e8220f90a02a030641d5c9f39d0402ac80154b6556ad2f54`。下述短路径均相对 `aiotbot-knowledge-wifi-mp/`。

## 结论与改动清单

| ID | 设计要求与行号 | 当前实现证据 | 最小调整 | 公开 seam 验证 |
|---|---|---|---|---|
| O1 | E0 在命令前按需发现能力；已加载项目上下文直接使用命令，不重新绑定。§1.0，9–23；§1.1，27–45；§5.1，405–409 | `workflows/common/knowledge/hs-knowledge-ingest/workflow.yaml:8–27` 把 `hs-workspace-explore` 和 `bind_project` 固定为入口；旧 lint Workflow 同样 `:8–27` 必须先绑定 | ingest 入口改为 P1 扫描／续办；E0 保留独立能力，接收已知路径，返回入口内容供 Agent 阅读；上下文已知不调用 E0 | 使用真实 host loader 装载 Workflow，入口必须为扫描节点；结构测试禁止 ingest 内出现 E0/bind_project；E0 既有 CLI 测试继续证明仓外 cwd 仅凭已知路径发现，不全盘扫描 |
| O2 | 一条 ingest 完成 P1–P7；lint 为独立只读 Skill，不另设 Workflow。§2.1，141–210；§6.3，738–751 | ingest Workflow `:85–127` 在 materialize 后转 `governance_handoff` 并结束，明确由用户另开 governance；`hs-knowledge-lint/workflow.yaml:33–321` 则拥有候选检查、真人确认、代码核验、apply、index、query、publish | 把必要确认／核验放回 P4；P5 调用 lint Skill；P6 记录；P7 apply→索引完整验证／目标查询→仓库提交。移除旧 lint Workflow 的活动安装与验证入口；可复用既有节点 Skill，不机械合并全部能力 | host loader 检查只有一条 ingest Workflow；图边覆盖 P5→P2/P3/P4、P5通过→P6→P7，以及等待／故障续办。不得存在第二次启动 lint Workflow 的要求；记录批可绕过卡片确认和索引步骤 |
| O3 | 默认 ingest 扫描五类 raw，`--source` 仅缩小范围；P1 先固定本批清单、完整性与未完成项。§1.2，68–94；§5.2，417–440 | 无 `hs-knowledge-source-scan` 包；`hs-knowledge-source-capture/scripts/capture.py:429–436` 强制 `source_id` 与单个 `source_path`，`:553–571` 只比较本次捕获来源与旧锁并登记维护事件。无法以无参 ingest 发现新增、改动、缺失和未完成范围 | 新增 `hs-knowledge-source-scan/scripts/scan.py`，只枚举五类允许目录，明确 optional source 范围；对照共享处理记录和本机停点，输出不可变批清单。区分 observed hash、已采用版本、已完成范围；不把一次捕获等同处理完成 | 从公开 CLI 用合成 K 测试首次全扫、增删改、相同hash但未完成、规则/证明失效、部分扫描、读失败／扫描失败、路径逃逸／链接；局部范围和不完整扫描均不得推出范围外删除 |
| O4 | P2 来源反查、主题搜索、明确依赖扩展；每卡恢复其实际采用版本，产出候选理由及材料。§5.2，429–445 | `governance/contracts/knowledge.py:43–139` 已能解析 sources/Claim，`:160–183` 仅验证 relation；未提供反向候选与依赖扩展接口。`hs-knowledge-maintain/scripts/maintain.py:287–318` 存在来源→受影响Claim遍历，但 `:299–300` 只处理 stable 且服务于限制事件。`hs-knowledge-change-plan/scripts/planning.py:41–58` 读取全卡，`:179–204` 接收作者提供的 bundle/decisions，未准备关联材料；`candidate_ids` 缺省还可从 decisions 自建，不能证明已覆盖扫描清单 | 在 `contracts/knowledge.py` 增加可重建的来源反查与明确依赖查询；P2 组合 capture/recover 与作者检索，输出 reading candidates（各状态）、关联理由、逐卡旧 snapshot、locator、diff；普通 related 不扩散。P3 发现新主题再回 P2。维护检索资格与回答资格分离；不添加本轮暂缓的新 search 索引时效检查 | 公开 prepare/material CLI：同源两卡采用不同 snapshot，均返回正确旧版；新 raw 无引用仍可给主题候选；draft/deprecated 等卡可进入整理候选；explicit dependency 扩展但 related 不扩展；材料缺失显示 gap；候选不自动产生更新决策 |
| O5 | P6 生成唯一共享 `logs/ingest` 记录，逐单元对账、固定校验，含 skip/defer/失败/未覆盖，P7 落位后补记。§5.6，562–589 | 不存在 source-scan/record.py 或 ingest-record 模板；`governance/contracts/records.py:6–28` 仅 seal/verify/schema/binding；`governance/schemas/records.schema.json:13–44` record_kind 枚举不含扫描清单／原件处理记录。维护 `logs/events` 和 `.build` 不是跨机处理记录 | 与治理侧统一 scan-manifest / ingest-record Schema、覆盖和引用校验。新增 `source-scan/scripts/record.py` 生成待提交记录，覆盖与进度由共用 records 函数校验，P7 真实落位后补记复验。卡关系仍从 cards/Claim/lock 重建。`.gitignore:20–29` 当前没有一刀切忽略 logs，因此无需无故放宽 logs 规则，只加明确本批提交清单 | 从公开 record CLI 测遗漏、重复、清单外自报、分段未覆盖、observed≠adopted、读失败无hash、skip理由/独立抽查、defer未完成、合法内容失败事实；仅记录批不伪造P5/确认/代码证明；record-only 不改卡/导航/lock；篡改已检卡须回P4/P5 |
| O6 | 宿主注册三个逻辑入口，已知上下文执行；同仓安装能力须匹配，不代表真实宿主已注册。§1.1，27–41；§7.2，812–814 | `hs-workspace-explore/scripts/install_catalog.py:22–44` 固定18 Skills与2 Workflows，缺 source-scan/lint Skill；`:365–389` 只复制 public CLI/Workflow 并生成 catalog，明确 Installation is not host registration。未观察到知识逻辑命令分派表 | catalog 安装新能力／单一Workflow，并显式导出 ingest/lint/query（及 status/index rebuild/recover）分派清单；分派适配已知K/config/rules。实际 host 注册保持单独验收，不为方便把“复制成功”写成“命令可用” | 新目录安装后从 catalog 调用新 CLI，loader加载唯一 Workflow；旧 lint 模板不可活动选择；包不含领域raw/knowledge/logs。维护入口可用；真实host命令触发需单独运行，无法执行则明确未验证 |
| O7 | 测试与验收应依据冻结设计，不冻结旧图 | `evals/validate_design.py:47–48,79–116,269–270,321,361–369` 固定bind_project入口、两套图及18个Skill；`evals/tests/test_workflows.py:67–91,167–169` 明确断言2 Workflow/18 Skills；`hs-workspace-explore/tests/test_install.py:70` 安装旧两Workflow | 改当前 evals 与Skill tests到新接口／图和公开seam；历史sdd v1/v2记录及原验收字节保持不动；保留现有upstream host loader校验和可信包执行检查 | 改后 validator/loader/CLI tests均实际运行；测试应验证节点关系、产物绑定、读写边界和续办，而非仅改数量让旧测试过绿 |

## 可直接保留的能力

- `hs-workspace-explore/scripts/node.py:27–100` 仅按给定路径向上找 config 或显式 registry，不全盘扫描；`:125–153` 读取并返回实际 AGENTS 内容与hash；`:204–236` 标明 discovery 上下文和缺口。这套 E0 能力可继续复用，主要错误在 Workflow 强制编排。
- capture 的确切字节、抽取定位、source resolution/recovery 能力已经存在，`capture.py:192` 的 `resolve_source` 及 `governance/contracts/source_resources.py:58` 的 `recover_snapshot` 应复用。
- 旧 change-plan 的六决策、baseline 与 authored request 可重演校验可保留；新增扫描覆盖与P3裁决证据应绑定在既有计划上，不让脚本代替 Agent 语义阅读。
- 现有按节点 `run_id/node_id/attempt_id` 不可变结果 manifest 仍可服务续办；不要以 host process exit 0 替代 status/phase/实际产物检查。

## 建议共享接口（待整合进 v3 设计，不直接改批准文档）

| 公开动作 | 输入关键引用 | 输出关键引用 | 所有权 |
|---|---|---|---|
| source-scan `scan` | 已知K/config/rules、可选source、可选operation | scan_ref/digest、scope/complete、单元ID与新增/修改/缺失/未完成/读失败、续办候选 | 扫描Skill；records定义结构与progress语义 |
| source-scan `prepare` 或 capture扩展动作 | scan_ref、待处理单元、可选主题候选/新增依赖查询 | material_ref/digest、current/old bytes引用、per-card adopted snapshots/Claim、reasons/gaps | 组合现有capture/recovery与knowledge关系函数；Agent继续主题阅读与搜索 |
| source-scan `record` | scan_ref、逐单元dispositions/coverage、可选plan/view/lint/独立抽查引用、actual progress | record_ref/digest（待提交内容）与固定校验结果 | 记录Skill；records统一验证；P7通过同一函数补记/复验 |
| host logical dispatch | 已知context + ingest/lint/query/maintenance参数 | Workflow或Skill调用目标、实际结果/停点 | 当前宿主适配；不改变OpenFlow引擎 |

record / manifest 推荐使用现有 seal、路径校验和规则身份机制，但新记录种类与既有schema版本的兼容由根任务治理负责人统一决定。P1扫描跳过与P3实质skip不同；后者必须包含本批独立风险抽查范围、结果及未抽范围。有限`--source`只限制处理范围，不能静默跳过必要的全库P5规则。

## 验证边界

本轮只读代码与合成测试源码，未运行测试，未断言当前18个Skill已经全部可用。没有读取安装机私人catalog或真实宿主配置；当前逻辑命令适配/真实host触发不能用仓内安装脚本证明。没有比较新search调用的索引当前性，该点按用户要求暂缓。没有修改或读取v1/v2历史正文以代替批准设计，也没有把本地fixture成绩当作真人、六Target、CI或ACL验收。
