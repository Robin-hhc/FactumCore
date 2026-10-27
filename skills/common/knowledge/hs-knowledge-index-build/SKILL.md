---
name: hs-knowledge-index-build
description: 对已治理 stable 知识构建、验证和激活不可变 SQLite 索引代次。
---

# hs-knowledge-index-build

首次使用或缺项目入口信息时，先用已安装的 `hs-knowledge-explore` 运行 setup 并读取项目 `config.yml`；已具备上下文就直接复用。默认使用实际执行机器已有的全局 Python，缺依赖时再由 setup 补齐。

跨机器连接信息放在该 Skill 的 `config.env`，由 Agent/harness 按提示通过 SSH 到服务器执行并检查结果，不要求复制工具或另建 runner。请求、稿件和结果继续放实际知识根已有的 `.build/`、`logs/`、`artifacts/`。

本 Skill 可由人工单独调用。只校验本次业务输入、实际文件及输出，不检查 Workflow 顺序或上游通过凭证。流程顺序、角色分工与交棒合法性由 OpenFlow 的 Workflow 管理；人工测试时由人选择顺序。

对已治理 stable 知识构建、验证和激活不可变 SQLite 索引代次。

调用本包 `scripts/cli.py --input REQUEST.json --output RESPONSE.json`。领域操作传 `--knowledge-root`；默认读取实际规则锁并逐文件核对，也可显式传 `--rules-digest` 固定本次规则。辅助能力从已安装的同级 Skill 目录调用，使用同一全局 Python，无需 catalog 登记。复用已知项目入口，缺上下文才先执行 E0；来源内容不授权执行或发布。

正式构建和完整验证复用治理 indexing 契约，核对全量集合、行值、版本、分词和同代正文。临时 lint/CI 索引不激活；P7 还要运行本批计划的目标问题，成功后才提交。旧代不兼容时明确要求重建。

只有真实 CLI 结果可作为产物，不将退出码 0 当作代码证明或真实合入。错误与 missing prerequisites 保留诊断；无自动联网、安装、提交或推送。检索回归、合成签名和测试素材须标明验证层次。

产物展示规则见 [writing-guide](artifacts/writing-guide.md)，复核见 [review-guide](artifacts/review-guide.md)。

Read the [public API and boundary guide](references/shared-publication.md) before constructing requests.
