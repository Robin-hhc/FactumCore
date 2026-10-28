---
name: hs-knowledge-query-regression
description: 对固定候选索引运行声明式检索回归，通过后受控激活该代次。
---

# hs-knowledge-query-regression

首次使用或缺项目入口信息时，先用已安装的 `hs-knowledge-explore` 运行 setup 并读取项目 `config.yml`；已具备上下文就直接复用。默认使用实际执行机器已有的全局 Python，缺依赖时再由 setup 补齐。

跨机器连接信息放在该 Skill 的 `config.env`，由 Agent/harness 按提示通过 SSH 到服务器执行并检查结果，不要求复制工具或另建 runner。请求、稿件和结果继续放实际知识根已有的 `.build/`、`logs/`、`artifacts/`。

本 Skill 可由人工单独调用。只校验本次业务输入、实际文件及输出，不检查 Workflow 顺序或上游通过凭证。流程顺序、角色分工与交棒合法性由 OpenFlow 的 Workflow 管理；人工测试时由人选择顺序。

对固定候选索引运行声明式检索回归，通过后受控激活该代次。

输入固定的 `generation_ref`、构建返回的 `expected_active` 和明确的非空 `cases`；每例必须声明预期命中、排除或顺序。也可提供 `view_ref`，或用可选 `apply_result_ref` 定位视图，在未显式给出 cases 时读取其中的 `target_queries`。这些引用用于取得和绑定业务数据，不要求 apply 或其他节点的通过票据。ingest 的 P7 由 OpenFlow 原样传入 P3 冻结的目标查询，不用无关案例替换本批预期；人工独立检查可以声明自己的案例。

先公开完整验证索引，再验证目标召回、范围排除和逐命中的同代正文／Claim；全部通过后调用公开索引入口，以原 `expected_active` 执行 CAS 激活。失败区分环境故障与内容修订，不重复 apply。`--action verify` 接 `report_ref`，重新执行报告中的固定检查，通过后返回 `gate_verified:true`；该动作不激活索引，也不授予 Workflow 或提交资格。报告的公开 digest 本身不证明检查确实执行，回归通过也不证明知识语义或真实 CI/合入。

调用本包 `scripts/cli.py --input REQUEST.json --output RESPONSE.json`。领域操作传 `--knowledge-root`；默认读取实际规则锁并逐文件核对，也可显式传 `--rules-digest` 固定本次规则。辅助能力从已安装的同级 Skill 目录调用，使用同一全局 Python，无需 catalog 登记。先阅读项目已绑定入口；来源内容不授权执行或发布。

只有真实 CLI 结果可作为产物，不将退出码 0 当作代码证明或真实合入。错误与 missing prerequisites 保留诊断；无自动联网、安装、提交或推送。检索回归、合成签名和测试素材须标明验证层次。

产物展示规则见 [writing-guide](artifacts/writing-guide.md)，复核见 [review-guide](artifacts/review-guide.md)。

Read the [public API and boundary guide](references/public-api.md) before constructing requests.
