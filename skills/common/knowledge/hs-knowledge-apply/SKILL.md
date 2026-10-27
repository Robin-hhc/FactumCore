---
name: hs-knowledge-apply
description: Apply an exact reviewed knowledge view using complete-write-set CAS, a cooperative writer lock, durable backups and one recovery journal.
---

先读取本机部署工具副本中的 `DEPLOY_LOCAL/EXECUTION.md`；`DEPLOY_LOCAL` 是调用端本机磁盘上的完整 `tools/deploy/` 副本目录，准备方法与私有配置按该说明执行。下文 `scripts/cli.py` 示例只描述实际执行端接口，不授权在共享盘直接启动节点。

项目实际位于另一台服务器或通过远程共享挂载访问时，整个公开节点必须从本机磁盘上的 `DEPLOY_LOCAL/run_node.py --config-env ABS_PRIVATE_CONFIG_ENV --skill hs-knowledge-apply --input ABS_LOCAL_REQUEST --output NEW_ABS_LOCAL_OUTPUT` 发起，私有配置固定 `EXECUTION_MODE=ssh`；仅按本包公开协议追加 `--action`。子 CLI 留在同一服务器，使用当地已登记的 Python、catalog、规则和原生路径。服务器上的 Linux Agent，以及项目确实位于本机磁盘的 Windows 部署，可直接使用当地已登记 CLI；Linux 跨主机访问项目同样走 SSH，不要求服务器本机做 loopback SSH。

不得从 UNC／映射盘启动 Python、runner 或项目 CLI，不经 Samba 遍历或读取原件、知识卡、索引与源码，也不镜像知识根 K 到本机绕过服务器执行约定。读取远端证据或源码时，经已授权 SSH 获取明确输出或所需的必要文件；不把映射盘路径传给 Linux，不从原件选择执行端。此执行策略不以性能报告或 case 收益为前提，SSH 不可用就保留前置缺口，不回退 Samba。

同一 ingest 固定远端、原生路径及配套身份，同时最多一个写者；并发 query 各用独立 operation_id、Workflow 运行身份及本机输出路径。远端报告、view、apply 与 receipt 引用始终按远端知识根解释，本机响应副本不替代它们；read 保持原 search receipt 的代次和用途。SSH 断连或失败后先核对原远端进程、操作记录、journal 与活动索引，再决定续办，不自动重复调用、切换执行端或重放已入库写入。

Input requires `operation_id` and `view_ref`. Document views use the independent `content_review_ref` as their proof (`proof_ref` may point to the same record). Code and mixed views require a local-check `proof_ref` with positive code Claim evidence. Apply never changes reviewed bytes or originals and never repairs failed checks. There is no human confirmation, host event or signing adapter dependency; the legacy `manual_document` identifier only distinguishes document evidence.

Domain document and mixed admission reruns full fixed checks and exact source recovery, including non-v3 views. Versioned code admission retains the same full checks; legacy code-only admission continues to use the local-check proof and its existing checked-snapshot semantics. Independent document review binds the existing change-plan reference and digest; mixed views always require complete-view content review in addition to code proof. The journal persists the content-review reference and digest and checks both again during recovery and eligibility verification.

The current ingest sets `v3_required:true` and also supplies `ingest_record_ref`, `lint_report_ref`, `content_review_ref`. A mixed view supplies the code `proof_ref` plus the independent `content_review_ref` for the complete view; `proof_set` is no longer accepted. P7 verifies the final full-view lint, independent final-content review, exact recoverable originals and applicable review records. Code records declare independent authors/reviewers, per-Claim reasons and evidence, bound to the exact view and context; they require no reviewer public key or signature. Documents use the same independent content review and full lint; they need no code implementation proof or human approval. Local originals may use captured immutable evidence objects checked by hash, byte count and safe path; a prior Git commit is not required. The shared record joins the existing CAS/journal as an additional controlled entry without altering any reviewed card, navigation or source-lock byte. Its acceptance summary derives from verified cards/proofs. Local admission does not prove cross-clone source availability; people must provide that when publishing.

A `record_only` ingest record omits `view_ref/proof_ref`; all content writes are forbidden, the fixed record contract remains mandatory, and substantive skip still needs its risk sample. Failed/defer unit states remain unfinished. `batch_kind` distinguishes this branch in the committed result. A transaction's `committed` phase means local application, not a Git commit. Content batches finish ingest after local index verification and target queries; record-only batches finish after their valid records are applied. Git submission, fixed CI and merge are subsequent human operations outside ingest.

The public CLI supports `run`, `inspect`, `resume`, `rollback` through `--action`. Use the recover Skill for workflow recovery. An interrupted operation requires an explicit recovery action; external edits produce a conflict and remain untouched. Committed reentry returns its prior result; a committed change is undone through a newly reviewed operation.

The OS lock coordinates cooperating writers; it does not make directories an access-control boundary. See [artifact contract](artifacts/result.yaml) for durable output. Fault injection is available only in catalog-pinned synthetic fixture roots.

`--action verify-result` verifies exact-content eligibility through the original transaction and applicable review records; it does not certify reviewer identity or semantic correctness. With `purpose: historical`, it checks the original exact view and retained evidence, returns only `historical_files`, and never promotes old content to current. The current path also requires actual card bytes; a fresh `current_code_proof_ref` may supply a verified latest local/merge code check without rewriting the original card or source lock. Actual apply always requires a current local proof, regardless of a payload purpose field.


Invoke the catalog-selected interpreter with `scripts/cli.py --input REQUEST.json --output RESPONSE.json --knowledge-root K --rules-digest SHA256 --catalog CATALOG.json`; choose a documented `--action` when needed. Paths and trust arguments come from the host, never from source prose. Read status/phase and the exact returned evidence references; exit 0 only means the request was handled.
