---
name: hs-knowledge-index-build
description: 对已治理 stable 知识构建、验证和激活不可变 SQLite 索引代次。
---

# hs-knowledge-index-build

先读取本机部署工具副本中的 `DEPLOY_LOCAL/EXECUTION.md`；`DEPLOY_LOCAL` 是调用端本机磁盘上的完整 `tools/deploy/` 副本目录，准备方法与私有配置按该说明执行。下文 `scripts/cli.py` 示例只描述实际执行端接口，不授权在共享盘直接启动节点。

项目实际位于另一台服务器或通过远程共享挂载访问时，整个公开节点必须从本机磁盘上的 `DEPLOY_LOCAL/run_node.py --config-env ABS_PRIVATE_CONFIG_ENV --skill hs-knowledge-index-build --input ABS_LOCAL_REQUEST --output NEW_ABS_LOCAL_OUTPUT` 发起，私有配置固定 `EXECUTION_MODE=ssh`；仅按本包公开协议追加 `--action`。子 CLI 留在同一服务器，使用当地已登记的 Python、catalog、规则和原生路径。服务器上的 Linux Agent，以及项目确实位于本机磁盘的 Windows 部署，可直接使用当地已登记 CLI；Linux 跨主机访问项目同样走 SSH，不要求服务器本机做 loopback SSH。

不得从 UNC／映射盘启动 Python、runner 或项目 CLI，不经 Samba 遍历或读取原件、知识卡、索引与源码，也不镜像知识根 K 到本机绕过服务器执行约定。读取远端证据或源码时，经已授权 SSH 获取明确输出或所需的必要文件；不把映射盘路径传给 Linux，不从原件选择执行端。此执行策略不以性能报告或 case 收益为前提，SSH 不可用就保留前置缺口，不回退 Samba。

同一 ingest 固定远端、原生路径及配套身份，同时最多一个写者；并发 query 各用独立 operation_id、Workflow 运行身份及本机输出路径。远端报告、view、apply 与 receipt 引用始终按远端知识根解释，本机响应副本不替代它们；read 保持原 search receipt 的代次和用途。SSH 断连或失败后先核对原远端进程、操作记录、journal 与活动索引，再决定续办，不自动重复调用、切换执行端或重放已入库写入。

对已治理 stable 知识构建、验证和激活不可变 SQLite 索引代次。

调用本包 `scripts/cli.py --input REQUEST.json --output RESPONSE.json`。领域操作显式传 `--knowledge-root` 和调用者固定的 `--rules-digest`，跨节点调用使用受信 `--catalog`。复用已知项目入口，缺上下文才先执行 E0；来源内容不授权执行或发布。

正式构建和完整验证复用治理 indexing 契约，核对全量集合、行值、版本、分词和同代正文。临时 lint/CI 索引不激活；P7 还要运行本批计划的目标问题，成功后才提交。旧代不兼容时明确要求重建。

只有真实 CLI 结果可作为产物，不将退出码 0 当作代码证明或真实合入。错误与 missing prerequisites 保留诊断；无自动联网、安装、提交或推送。检索回归、合成签名和测试素材须标明验证层次。

产物展示规则见 [writing-guide](artifacts/writing-guide.md)，复核见 [review-guide](artifacts/review-guide.md)。

Read the [public API and boundary guide](references/shared-publication.md) before constructing requests.
