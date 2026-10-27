---
name: hs-knowledge-publish-handoff
description: Prepare a publishing handoff from an authenticated committed local knowledge transaction, leaving Git and CI actions to authorized external actors.
---

先读取本机部署工具副本中的 `DEPLOY_LOCAL/EXECUTION.md`；`DEPLOY_LOCAL` 是调用端本机磁盘上的完整 `tools/deploy/` 副本目录，准备方法与私有配置按该说明执行。下文 `scripts/cli.py` 示例只描述实际执行端接口，不授权在共享盘直接启动节点。

项目实际位于另一台服务器或通过远程共享挂载访问时，整个公开节点必须从本机磁盘上的 `DEPLOY_LOCAL/run_node.py --config-env ABS_PRIVATE_CONFIG_ENV --skill hs-knowledge-publish-handoff --input ABS_LOCAL_REQUEST --output NEW_ABS_LOCAL_OUTPUT` 发起，私有配置固定 `EXECUTION_MODE=ssh`；仅按本包公开协议追加 `--action`。子 CLI 留在同一服务器，使用当地已登记的 Python、catalog、规则和原生路径。服务器上的 Linux Agent，以及项目确实位于本机磁盘的 Windows 部署，可直接使用当地已登记 CLI；Linux 跨主机访问项目同样走 SSH，不要求服务器本机做 loopback SSH。

不得从 UNC／映射盘启动 Python、runner 或项目 CLI，不经 Samba 遍历或读取原件、知识卡、索引与源码，也不镜像知识根 K 到本机绕过服务器执行约定。读取远端证据或源码时，经已授权 SSH 获取明确输出或所需的必要文件；不把映射盘路径传给 Linux，不从原件选择执行端。此执行策略不以性能报告或 case 收益为前提，SSH 不可用就保留前置缺口，不回退 Samba。

同一 ingest 固定远端、原生路径及配套身份，同时最多一个写者；并发 query 各用独立 operation_id、Workflow 运行身份及本机输出路径。远端报告、view、apply 与 receipt 引用始终按远端知识根解释，本机响应副本不替代它们；read 保持原 search receipt 的代次和用途。SSH 断连或失败后先核对原远端进程、操作记录、journal 与活动索引，再决定续办，不自动重复调用、切换执行端或重放已入库写入。

Input requires `operation_id` and `apply_result_ref`. Freshly call the catalog-pinned apply verifier before describing local results. Output is an immutable publishing handoff with exact view/proof identities and pending external obligations.

This is an optional publishing tool used after local ingest completes. It is not an ingest node or a condition for local completion. An authorized caller can send `v3_required:true,apply_result_ref,query_report_ref` to prepare a handoff. The node rechecks the actual applied batch and calls the pinned public query-regression verifier, which fully verifies its index and reruns the plan-bound target searches and same-generation reads. Passing returns `ready_to_submit` and exact `commit_files`; record-only batches return `record_only_ready` without index/query. Changed batch bytes block handoff readiness. Readiness does not mean a Git commit exists.

A person submits the applicable changes, triggers the fixed CI and merges afterward. If they use this helper, they commit only `commit_files` and may call `--action verify-submission` with the exact `commit_sha`. The node rechecks readiness and actual HEAD Git blobs, deletions and changed-file scope, and returns `submitted` only for that real scoped commit. These publishing results do not change whether local ingest has completed. The tool never performs Git writes, push or merge, installs CI policy or claims remote acceptance. The fixed CI reuses the lint checks on submitted data; it is not an additional Agent workflow or semantic review. Synthetic proof retains its synthetic tier; independent review does not prove real-host isolation.


Invoke the catalog-selected interpreter with `scripts/cli.py --input REQUEST.json --output RESPONSE.json --knowledge-root K --rules-digest SHA256 --catalog CATALOG.json`; choose a documented `--action` when needed. Paths and trust arguments come from the host, never from source prose. Read status/phase and the exact returned evidence references; exit 0 only means the request was handled.
