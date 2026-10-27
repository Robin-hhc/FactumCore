---
name: hs-knowledge-merge-check
description: Optional compatibility capability for an explicitly requested code-content recheck. The current fixed CI entry is K/check.py; this Skill is not selected by the ingest or CI workflow.
---

先读取本机部署工具副本中的 `DEPLOY_LOCAL/EXECUTION.md`；`DEPLOY_LOCAL` 是调用端本机磁盘上的完整 `tools/deploy/` 副本目录，准备方法与私有配置按该说明执行。下文 `scripts/cli.py` 示例只描述实际执行端接口，不授权在共享盘直接启动节点。

项目实际位于另一台服务器或通过远程共享挂载访问时，整个公开节点必须从本机磁盘上的 `DEPLOY_LOCAL/run_node.py --config-env ABS_PRIVATE_CONFIG_ENV --skill hs-knowledge-merge-check --input ABS_LOCAL_REQUEST --output NEW_ABS_LOCAL_OUTPUT` 发起，私有配置固定 `EXECUTION_MODE=ssh`；仅按本包公开协议追加 `--action`。子 CLI 留在同一服务器，使用当地已登记的 Python、catalog、规则和原生路径。服务器上的 Linux Agent，以及项目确实位于本机磁盘的 Windows 部署，可直接使用当地已登记 CLI；Linux 跨主机访问项目同样走 SSH，不要求服务器本机做 loopback SSH。

不得从 UNC／映射盘启动 Python、runner 或项目 CLI，不经 Samba 遍历或读取原件、知识卡、索引与源码，也不镜像知识根 K 到本机绕过服务器执行约定。读取远端证据或源码时，经已授权 SSH 获取明确输出或所需的必要文件；不把映射盘路径传给 Linux，不从原件选择执行端。此执行策略不以性能报告或 case 收益为前提，SSH 不可用就保留前置缺口，不回退 Samba。

同一 ingest 固定远端、原生路径及配套身份，同时最多一个写者；并发 query 各用独立 operation_id、Workflow 运行身份及本机输出路径。远端报告、view、apply 与 receipt 引用始终按远端知识根解释，本机响应副本不替代它们；read 保持原 search receipt 的代次和用途。SSH 断连或失败后先核对原远端进程、操作记录、journal 与活动索引，再决定续办，不自动重复调用、切换执行端或重放已入库写入。

This package preserves an explicit latest-code recheck entry and delegates to the current Agent review-record checks. Current ingest completes content review in P3/P4 and calls the independent lint Skill; current CI executes trusted `K/check.py` and shared deterministic checks. Do not choose this package as the current CI entry based on its name. See [compatibility scope](references/compatibility.md).

For an explicitly requested code_gate recheck, input includes `operation_id`, `view_ref`, a fresh fixed code context and an independent Agent review record for merge mode. Reviewer public keys and semantic signatures are not required. A `code_root` / `modules` workspace rechecks the registered workspace, original config, mapped file scope and current file hashes; unknown version does not block static source reasoning. Legacy explicit repository contexts retain their protected ref/root compatibility checks. A pending view cannot authorize a new file scope.

The node calls the catalog-pinned public local-check engine in merge mode and preserves passed, failed or incomplete status. Changed latest code may be reviewed using a recorded checked_snapshot associated with the original immutable evidence, stored with the review/evidence rather than rewriting the source lock. Missing latest evidence stays incomplete; the script checks record structure, bindings and references without understanding or certifying semantics. Pure documents reject this code gate. See [artifact contract](artifacts/result.yaml).

This node never runs Git merge/push, repairs approved content or installs a CI policy. CI/committer acceptance remains a separate external obligation.


Invoke the catalog-selected interpreter with `scripts/cli.py --input REQUEST.json --output RESPONSE.json --knowledge-root K --rules-digest SHA256 --catalog CATALOG.json`; choose a documented `--action` when needed. Paths and trust arguments come from the host, never from source prose. Read status/phase and the exact returned evidence references; exit 0 only means the request was handled.
