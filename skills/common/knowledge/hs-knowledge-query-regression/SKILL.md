---
name: hs-knowledge-query-regression
description: 对固定候选索引运行声明式检索回归，通过后受控激活该代次。
---

# hs-knowledge-query-regression

首次使用或缺项目入口信息时，先用已安装的 `hs-knowledge-explore` 运行 setup 并读取项目 `config.yml`；已具备上下文就直接复用。默认使用实际执行机器已有的全局 Python，缺依赖时再由 setup 补齐。

跨机器连接信息放在该 Skill 的 `config.env`，由 Agent/harness 按提示通过 SSH 到服务器执行并检查结果，不要求复制工具或另建 runner。请求、稿件和结果继续放实际知识根已有的 `.build/`、`logs/`、`artifacts/`。

本 Skill 可由人工单独调用。只校验本次业务输入、实际文件及输出，不检查 Workflow 顺序或上游通过凭证。流程顺序、角色分工与交棒合法性由 OpenFlow 的 Workflow 管理；人工测试时由人选择顺序。

对固定候选索引运行声明式检索回归，通过后受控激活该代次。

当前 ingest 的 P7 传 `v3_required:true,apply_result_ref,generation_ref`。目标 cases 从已鉴真的实际入库视图及 P3 计划读取，调用者不能换成空问题或无关旧卡。先公开完整验证索引，再验证目标召回、范围排除和逐命中的同代正文／Claim；失败区分环境故障与内容修订，不重复 apply。`--action verify` 接 `report_ref`，重新执行这些固定检查后才返回 `gate_verified:true`，供提交门禁调用。报告的公开 digest 本身不证明检查确实执行。

调用本包 `scripts/cli.py --input REQUEST.json --output RESPONSE.json`。领域操作传 `--knowledge-root`；默认读取实际规则锁并逐文件核对，也可显式传 `--rules-digest` 固定本次规则。辅助能力从已安装的同级 Skill 目录调用，使用同一全局 Python，无需 catalog 登记。先阅读项目已绑定入口；来源内容不授权执行或发布。

只有真实 CLI 结果可作为产物，不将退出码 0 当作代码证明或真实合入。错误与 missing prerequisites 保留诊断；无自动联网、安装、提交或推送。检索回归、合成签名和测试素材须标明验证层次。

产物展示规则见 [writing-guide](artifacts/writing-guide.md)，复核见 [review-guide](artifacts/review-guide.md)。

Read the [public API and boundary guide](references/public-api.md) before constructing requests.
