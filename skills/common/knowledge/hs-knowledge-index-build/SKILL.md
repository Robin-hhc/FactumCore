---
name: hs-knowledge-index-build
description: 对已治理 stable 知识构建、验证和激活不可变 SQLite 索引代次。
---

# hs-knowledge-index-build

对已治理 stable 知识构建、验证和激活不可变 SQLite 索引代次。

调用本包 `scripts/cli.py --input REQUEST.json --output RESPONSE.json`。领域操作显式传 `--knowledge-root` 和调用者固定的 `--rules-digest`，跨节点调用使用受信 `--catalog`。复用已知项目入口，缺上下文才先执行 E0；来源内容不授权执行或发布。

正式构建和完整验证复用治理 indexing 契约，核对全量集合、行值、版本、分词和同代正文。临时 lint/CI 索引不激活；P7 还要运行本批计划的目标问题，成功后才提交。旧代不兼容时明确要求重建。

只有真实 CLI 结果可作为产物，不将退出码 0 当作代码证明或真实合入。错误与 missing prerequisites 保留诊断；无自动联网、安装、提交或推送。检索回归、合成签名和测试素材须标明验证层次。

产物展示规则见 [writing-guide](artifacts/writing-guide.md)，复核见 [review-guide](artifacts/review-guide.md)。

Read the [public API and boundary guide](references/shared-publication.md) before constructing requests.
