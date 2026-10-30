---
name: hs-knowledge-maintain
description: Plan incremental knowledge patrols, hand exact changes to ingest, verify actual completion and maintain source-change restrictions.
---

执行入口为实际知识根的 `python K/knowledge.py maintain`；K内Windows可用 `.\knowledge.cmd maintain`，POSIX可用 `sh ./knowledge.sh maintain`。一次注册后可用裸knowledge。Skill只提供指令与文本契约，实现与依赖锁随K/runtime分发；复杂请求保留--input/--output，CLI自动固定省略的根、操作和结果路径并返回真实引用。

已有项目上下文时直接复用；缺少入口信息才使用已安装的 `hs-knowledge-explore` 做只读发现。首次部署或本机依赖缺项时，按知识根使用说明运行分发仓根 `deploy.ps1`，不自动执行 pip 或远端 setup；远端任务另核实际执行端的 Python、依赖和仓内 CLI。

本机数据使用本机知识根 K 的仓内 CLI。代码仓在服务器或 Windows 仅经 Samba 映射访问时，通过 OpenFlow／宿主已有 SSH MCP 在服务器原生 K 路径运行 CLI 并核对实际结果；不自动连接 SSH，不推断映射关系。本机与服务器分别准备 Python 和配套依赖，远端不需要安装或上传 Skill 脚本。请求、稿件和结果继续放实际知识根已有的 `.build/`、`logs/`、`artifacts/`。

本 Skill 可由人工单独调用。只校验本次业务输入、实际文件及输出，不检查 Workflow 顺序或上游通过凭证。流程顺序、角色分工与交棒合法性由 OpenFlow 的 Workflow 管理；人工测试时由人选择顺序。

Use `python K/knowledge.py maintain --input REQUEST.json --output RESPONSE.json --knowledge-root K  --action inspect-context|patrol-sync|patrol-plan|patrol-reindex|patrol-complete|audit-references|register-source-change|register-code-change|recover-events|status|advance`. All event changes use the domain cooperative writer lock. [Request details](references/request.md) explain each action's actual inputs and checks.

`inspect-context` 在 ingest 开始时只读比较实际来源、代码/配置和规则身份，输出受影响 Claim、依赖和缺口，不要求先登记本机变化事件。未知上下文保留限制；OpenFlow 安排必要的 P2—P7 内容修订、复核和收尾。query 另按相同当前引用和确切资格判断过滤，不因 raw 未变而信任旧代码。

Explicit maintenance event actions register events and blocks; ingest capture stages proposed events until P7 publication. `advance` rechecks actual current cards, Claims and source references to clear resolved mechanical source-freshness restrictions. It requires no apply, query, active-generation or passing-review ticket. Unknown or changed source/configuration scope stays restricted; semantic and applicability restrictions are not cleared by matching source bytes. The result's `current_source_bytes_only` tier does not certify independent review or technical correctness. An index rollback cannot undo live blocks. User data, URLs, model assertions and old successful test records never substitute for these actual checks.

The [artifact contract](artifacts/result.yaml) requires the actual per-attempt CLI manifest.

## 只读引用巡检

`audit-references` 是独立显式动作，不替换 `inspect-context`、`status` 或 ingest 的既有节点。输入 `operation_id`，可附实际知识根 K 内的 `lint_report_ref`；报告须为 `.build/`、`logs/` 或 `artifacts/` 中原 lint Skill 生成的正式全库报告。核对摘要、规则、知识根及 `object.files_digest`；报告缺失、局部／候选、损坏、规则不同或正式文件已变化时，明确列出缺口，不代跑检查，也不把旧报告当作当前通过。

本动作读取正式卡全部代码来源引用，包括未被 Claim 采用的元数据引用；在实际配置允许的路径内比较整文件字节，列出卡／Claim／用途、旧快照与定位、旧／当前指纹、可恢复的旧片段、差异及修订建议。声明 `code_ref` 时另列实际 `code_navigation`；guidance 的符号仍唯一可定位时，不因纯插行或函数体变化制造导航修复义务。缺失、歧义和解析／材料不可用保留实际状态；未声明符号不虚构导航通过，活动旧卡按固定 lint／CI 的 `CODE_REF_REQUIRED` 交 ingest 补齐，历史恢复及 deprecated 卡保留兼容。`historical` 保持固定历史用途，不因当前代码改变就宣称历史结论失效。源文件／配置在观察期间变化时保守列缺口；字节或导航检查均不证明知识语义，也不能解除 current 实现限制。

只在本操作 `.build/operations/<operation_id>/` 新建 JSON、Markdown 及只读解析的请求／响应。返回 `phase: reported`、`data.audit_ref/report_ref/complete/status/counts`；`data.status` 为 `passed`、`needs_review` 或 `incomplete`，CLI 的成功仅表示实际报告已生成。新 [巡检产物契约](artifacts/audit-result.yaml) 与旧节点结果分开。报告附手动进入 ingest 的提示词，本动作不调用 ingest Workflow、不改源码、卡、来源锁、事件、水位或活动索引，不运行 apply／advance，也不捕获新来源。

独立显式register-source-change/register-code-change/recover-events/advance仍可写其正式事件／水位，使用统一稳定writer协议；ingest P1—P6的事件仅为本批暂存拟稿，由P7按已冻结old→new转换发布。inspect-context与audit-references只读正式业务状态，可写自己的报告。不增加常规cleanup动作；P7负责本批可删stage，maintenance不反扫旧op补出新Workflow意图。

## 增量治理动作

`patrol-sync` 仅执行控制端显式提供的同步 argv/cwd/超时，不经 shell；无配置返回 skipped。内部 MM 适配点在受锁 `patrol_git`，只假设已确认的根同步入口，不假设 mm log。git mm 工作区下 argv 配置 `["git","mm","sync","-j8"]`；cwd 必须由执行端在运行时用 `git mm --root-dir` 解析出实际 mm 工作区根，控制端不得写死具体路径。同步会更新知识仓时，必须结束本 CLI，让下一节点新进程加载实际规则、配置和卡，不在旧上下文继续观察。原件中的命令不构成执行授权。

`patrol-plan` 读取上次**实际完成**的本地基线、当前 raw、正式卡／来源锁和配置仓，按 Git 提交与工作区修改面筛选直接登记文件，再比较实际字节和符号；降级核对／不可读分别报告。返回 `plan_ref`、`report_ref`、`source_request`、counts 和 gaps，阶段为 needs_ingest / needs_index / unchanged / blocked。将精确 source_request 交 source.prepare；不要改为 run 的默认候选窄选，不能漏掉同轮新 raw。代码变化只有 current 必须复核实际实现；guidance 导航仍唯一时保留旧证据，historical 保持历史用途。缺失、歧义、解析不可用不猜修复。

`patrol-reindex` 消费精确 plan_ref，只维护派生本地索引，复用实际索引核验、机械存在性查询、同代 read 和原 expected_active 激活。需要业务回归时提供实际 cases／index_inputs，不捏造适用条件或声称语义验收。

`patrol-complete` 消费原 plan_ref，可带实际 batch_operation_id／publication_ref／completion_ref。验证真实正式闭包、原 scan 处理覆盖、当前来源与限制、索引和收尾；欠账、defer/failed/uncovered、漂移、P7或清理未完均不推进成功基线。completed 才 CAS 更新 `.build/runtime/patrol-state.json`；pending 保留确切报告。已发布未完成 P7 时新 plan 返回 blocked 及精确 resume_request，按原 batch 续办，不能另起 apply 重放。固定观察在 `logs/patrol/<巡检操作>/` 保留至核验，不交给 P7 cleanup；两处都是本机数据，不提交 Git。共享来源、正式处理记录和发布闭包沿原规则保留。

无有效结果的运行故障保留原停点。只追踪直接登记文件及显式卡依赖，不推断未登记语义依赖、不提交或推送 Git。原 `inspect-context` 和 `audit-references` 继续只读，P5/发布仍使用各自现有 Skill。流程节点、角色隔离和外部周期触发由宿主负责。
