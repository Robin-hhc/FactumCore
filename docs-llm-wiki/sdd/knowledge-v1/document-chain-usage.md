# raw 文档手工操作链

本说明按 FactumCore 单仓根当前公开 CLI 编写：T03 捕获与恢复，T05 计划与最终视图，T06 真实人工确认与部分接受，T07 本地事务落位，包含已公开的 `ingest apply`。使用旧版本时先核对该 checkout 的 `ingest --help` 及实际验收记录，未注册 apply 的旧版本应停在已确认阶段。本文不修改任务状态，也不表示完整 Skill/Workflow 自动编排或真实业务部署已经验收。

## 输入、环境与范围

操作者先确认对原件和目标领域的授权，再自行将文件放入 `aiot-wifi-knowledge/docs-raw/` 的 conventions、chips、storys、specs、protocols 五类之一。首发不沿 sources 链接、URL、wiki、3ms 或仓外 dbox 地址取文档；dbox 等资料须由人先落地到允许 raw 目录。

主件仅支持 UTF-8 的 `.md`、`.txt`（含 UTF-8 BOM），保留原字节并生成文本和定位映射。PDF/Word 不支持作为主件，不将改后缀视作格式转换。二进制附件可以随主件保存原字节，但没有文本、图表理解或 OCR 证明；需要这些信息才能判断的断言应暂缓或补充可核对材料。

主件和所有附件都须处于上述允许根；控制文件 AGENTS.md/index.md、越界符号链接或 junction 不作原件。Markdown 本地引用的文件必须存在并通过 `--attachment` 逐个声明。原文中的远端链接保留为文字，不会被访问，也不等于其内容已捕获。

在仓根使用 Python 3.12，按锁安装依赖：

```powershell
Set-Location 'E:\FactumCore' # 按实际 checkout 位置修改
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.lock.txt
```

以下变量中的 `<...>` 必须由操作者填写后才执行，命令不会替你取得业务资料或编造知识卡。`operation_id` 使用 1–64 位字母、数字、下划线或连字符，以字母或数字开头；内容或决定改变时使用新 ID。

```powershell
$repo = 'E:\FactumCore'
$python = Join-Path $repo '.venv/Scripts/python.exe'
$cli = Join-Path $repo 'skills/common/knowledge/_shared/cli.py'
$knowledgeRoot = Join-Path $repo 'aiot-wifi-knowledge'
$rawPath = 'docs-raw/specs/<document-id>/<version-or-digest>/<original.md>'
$sourceId = '<stable-logical-source-id>'
$operationId = '<unique-operation-id>'
$candidate = Join-Path $repo 'artifacts/manual/<candidate-file>.md'
$targetPath = 'knowledge/glossaries/<card-file>.md'
```

`$rawPath` 和 `$targetPath` 相对领域根；`$candidate` 是作者编写的 Markdown 路径。以下用 glossary 演示路径选择，不提供真实结论。工具路径与领域根均为绝对路径，因此配置这些变量后可从其他 cwd 调用。

## 1. T03：固定 raw 原件与附件

```powershell
$captureOutput = & $python $cli document capture `
  --knowledge-root $knowledgeRoot --path $rawPath `
  --source-id $sourceId --declared-version 'unknown'
if ($LASTEXITCODE -ne 0) { throw $captureOutput }
$capture = ($captureOutput | ConvertFrom-Json).result
$bundleRef = $capture.bundle_ref
$manifestDigest = $capture.manifest_digest
$capture.snapshots | Select-Object source_id, snapshot_id
```

确有可靠版本时替换 declared-version，未知保持 unknown，不以 mtime 补造平台版本。source_id 延续同一逻辑资料，snapshot_id 固定本次实际字节。存在附件时，在 capture 命令添加可重复参数：

```powershell
# 添加到上面的 capture 调用；每项都是相对领域根的实际文件路径。
# --attachment 'docs-raw/specs/<document-id>/<version-or-digest>/<attachment-file>'
```

捕获成功返回 resources、snapshots、members、bundle_ref 和 manifest_digest。持久证据位于 `logs/evidence/<bundle_id>/`，包含 manifest、原始对象和派生文本/locator。此步不写正式知识卡、来源锁或导航。原件移动后，使用保留的包引用和摘要核验恢复：

```powershell
& $python $cli document load-capture --knowledge-root $knowledgeRoot `
  --bundle-ref $bundleRef --manifest-digest $manifestDigest
if ($LASTEXITCODE -ne 0) { throw '持久证据核验失败，停止后续操作。' }
```

load-capture 从保留包取回确切字节和分析结果，不沿旧路径重新摄入，也不会把已修改的 raw 偷换成旧证据。保留 bundle_ref、manifest_digest 和持久包，不能只依赖可删的 `.build/` 或本地索引。

## 2. 作者编写显式候选

从 [七类模板](../../../aiot-wifi-knowledge/governance/templates/) 选择匹配问题的 Profile。以 glossary 为例，将 `governance/templates/glossary.md` 复制到 `$candidate` 后，由作者或 Agent 基于已捕获材料填写完整正文；程序不把原文自动摘录为语义正确的知识卡。

| Profile | target-path 前缀 |
|---|---|
| entity | knowledge/concepts/entities/ |
| flow | knowledge/concepts/flows/ |
| protocol | knowledge/concepts/protocols/ |
| rule | knowledge/rules/ |
| command | knowledge/commands/ |
| runbook | knowledge/runbooks/ |
| glossary | knowledge/glossaries/ |

填完所有 `{{...}}`，保留 draft/manual_document，明确 card_id、Claim ID、owner、章节和正文定位。每个 Claim 必须有来源；Card.sources 填本次返回的固定 **snapshot_id**，Claim.source_ids 填相应逻辑 **source_id**，两者不互换；引用附件事实时选择其独立快照。候选至少关联本次捕获的一个快照。来源不足就 defer，不为通过解析编造证据。

Claim.text_ref 使用独占一行的显式 `<a id="..."></a>` 所指 `#...`，或正文 `lines:起行-止行`；保留模板必需章节。scope/context 只写实际有据的范围，unknown 不等于六 Target 通用。规范细节见 [cards.md](../../../aiot-wifi-knowledge/governance/specs/cards.md)。结构检查不证明文档结论、当前产品实现或实测结果。

## 3. T05：明确决策，生成确切最终视图

```powershell
& $python $cli ingest plan --knowledge-root $knowledgeRoot `
  --operation-id $operationId --bundle-ref $bundleRef `
  --manifest-digest $manifestDigest --decision create `
  --rationale '<为什么是独立问题、证据与范围如何支持>' `
  --target-path $targetPath --candidate $candidate
if ($LASTEXITCODE -ne 0) { throw '计划失败，请先处理诊断。' }

& $python $cli ingest materialize --knowledge-root $knowledgeRoot `
  --operation-id $operationId
if ($LASTEXITCODE -ne 0) { throw '最终视图生成失败。' }
```

本批对单卡 create/update 生成可确认的 final-view。create 要求目标尚不存在；update 要求已有目标且保留同一 Card ID。merge、split、deprecate 可记录计划但仅返回 planned_only，复杂跨卡执行属于 T09；defer/no_change 返回对应结束阶段，不生成可 apply 的确认包。关联卡可用重复 `--related-card-id` 记录，不能凭同名或同来源自动合并。

产物位于 `K/.build/<operation_id>/`：plan.json、candidates/card.md、changeset.json、final-view/ 和 review-package.md。final-view 已含拟落位 stable 的卡片、导航和来源锁的确切字节；此时正式目录仍未修改。操作者检查差异包及源文本，确认其中每个拟写文件都在预期范围。相同输入重复运行幂等，不能以同一个 operation_id 替换另一份候选。

## 4. T06：真实人确认当前最终视图

本步必须由真实贡献者在其控制的交互终端直接执行和输入。贡献者可确认自己的文档，不要求额外审批人。Agent 不得代填挑战或把自动创建的 PTY 当成人工动作；终端访问和记录目录写权限由宿主控制，程序检查 TTY 与挑战，不认证操作者身份。

```powershell
# 由真人直接执行；保持 stdin 连接交互终端，不管道输入回答。
& $python $cli document confirm --knowledge-root $knowledgeRoot `
  --operation-id $operationId --decision accepted `
  --confirmed-by '<贡献者自报身份>'
```

终端展示最终文件、源文本、摘要和二进制附件限制，并要求输入 `accepted <当前final_view_digest前12位>`。真人读完后按实际显示内容输入；不要复制旧摘要。`--confirmed-by` 仅记录自报名字，单独给名字不会批准；没有 `--yes`、名字即批准或 JSON 批准入口。无回复、超时、非 TTY、输入不匹配都不能成为确认。聊天中的“同意”尚无可信适配器接入本 CLI，不能代写成已确认 JSON。

成功 JSON 的 result 返回 review_ref、review_digest、decision 与 phase。人工记录保存于 `logs/document-reviews/review-<id>.json`，绑定 operation、确切 final-view、来源集合、scope、相关基线、工具及契约。记录本次返回的真实 review_ref，例如：

```powershell
$reviewRef = 'logs/document-reviews/<实际返回的review-id>.json'
```

| decision | 后续动作 |
|---|---|
| accepted / confirmed_no_impact | 覆盖整个确切最终视图，才可进入 apply；后者仍须真人核对，不是自动免确认 |
| partially_accepted | 只能进入缩窄新视图与重新确认，不得 apply 原视图 |
| returned / deferred | 返回作者修订或暂缓，不授权落位 |
| deprecated | 记录人工决定，不自动执行跨卡废弃；本批不据此 apply |

### 部分接受：严格子集、新操作、再次真人确认

存在多个 Claim 时，真人可通过 `--claim-id` 明确选择要保留的非空严格子集，每项一个参数；若未传此参数，可在随后显式编写的新视图选择严格子集，但新视图仍须再次真人确认。以下演示提前选择保留项，未知 ID 会被拒绝：

```powershell
& $python $cli document confirm --knowledge-root $knowledgeRoot `
  --operation-id $operationId --decision partially_accepted `
  --confirmed-by '<贡献者自报身份>' --claim-id '<保留的Claim-ID>'
# 真人输入本次显示的 partially_accepted 挑战；记下返回的 review_ref。
```

作者另写缩窄候选，保留同一 Card ID、scope 和被选 Claim 的元数据及正文片段，不引入新来源；去掉未接受断言。新候选恰好保留真人选择的 Claim 子集，若需改写保留断言，应走新显式计划。然后：

```powershell
$partialReviewRef = 'logs/document-reviews/<实际部分接受的review-id>.json'
$newOperationId = '<新的operation-id>'
$narrowCandidate = Join-Path $repo 'artifacts/manual/<缩窄后的candidate-file>.md'
& $python $cli document narrow --knowledge-root $knowledgeRoot `
  --operation-id $operationId --review-ref $partialReviewRef `
  --new-operation-id $newOperationId --candidate $narrowCandidate
if ($LASTEXITCODE -ne 0) { throw '缩窄失败，未授权任何正式写入。' }

# narrow 已生成新的 plan/final-view；必须由真人再次读完并确认新的摘要。
& $python $cli document confirm --knowledge-root $knowledgeRoot `
  --operation-id $newOperationId --decision accepted `
  --confirmed-by '<贡献者自报身份>'

# 第二次真人 accepted 成功后，后续 apply 使用这组新身份。
$operationId = $newOperationId
$reviewRef = 'logs/document-reviews/<第二次accepted实际返回的review-id>.json'
```

后续使用 **newOperationId 与第二次 accepted 返回的 review_ref**；旧部分接受记录既不批准原全量视图，也不自动批准新视图。只有一个 Claim 的卡无法形成非空严格子集，应整体接受、退回或暂缓。

## 5. T07：本地 stable 事务落位

当前 CLI 已公开此命令，模块实际验收状态查任务与记录。如走过 narrow，先令 operationId/reviewRef 指向新操作和第二次确认记录。

```powershell
& $python $cli ingest apply --knowledge-root $knowledgeRoot `
  --operation-id $operationId --review-ref $reviewRef
if ($LASTEXITCODE -ne 0) { throw '落位失败，请保留操作目录和诊断。' }
```

apply 只接受本次确切视图的有效完整人工确认，经写锁、相关基线 CAS、全域 ID/关系一致性检查及备份/journal 后，写入已列明的正式 stable 卡、来源锁与导航。确认后任一正文、来源、scope、相关基线、工具或契约变化，都不能沿用旧批准。

唯一事务材料持久保留在 `K/logs/operations/<operation_id>/`：journal.json、backup-manifest.json、backups/ 与 result.json；备份名为目标相对路径的 SHA-256。它们不随 `.build/` 候选清理，不在原设计的 `.build/<operation_id>/transaction/` 再保留第二套 journal。写锁是 `K/logs/operations/.writer.lock`；锁文件存在不等于进程仍持锁，不能据文件存在直接删除。

落位成功是本地 stable：不执行 Git commit/merge/push，不构建索引、不激活 local/shared，也不证明最新代码正确。上库与共享发布是另行授权、单独记录的步骤；当前资料路径和文件清单不能说明已可检索。此纯文档链不运行代码两门禁。

## 诊断与中断处理

公开命令返回 JSON：顶层 status=ok/invalid/error 分别对应退出码 0/2/3。查看 diagnostics[].code/message/path；顶层 ok 仍须检查 result.phase，例如 planned_only、deferred、no_change 不代表可落位。confirm 的审阅内容和挑战显示在 stderr，最终 JSON 在 stdout，别把只看到 JSON 当成真人已读证据。

| 情况或诊断 | 处理 |
|---|---|
| DOCUMENT_SOURCE_DEFERRED / UNSUPPORTED_DOCUMENT_FORMAT / SOURCE_PATH_ESCAPE | 检查是否真实落地、五类目录、支持格式及路径边界；不要改配置绕过范围 |
| ATTACHMENT_MISSING / ATTACHMENT_NOT_DECLARED / UNSUPPORTED_MARKDOWN_LINK | 补齐本地必要附件及显式声明，或改成当前支持的可核对表达；随后重新 capture |
| SOURCE_CHANGED / EVIDENCE_INTEGRITY_ERROR | 停止后续使用；固定稳定原件或从受保留副本恢复证据包，保留旧包和诊断，不覆盖损坏包假装成功 |
| CANDIDATE_REQUIRED / EVIDENCE_REQUIRED / 引用或锚点错误 | 作者补齐完整候选、快照/逻辑来源映射和定位；证据不足用 defer |
| OPERATION_CONFLICT / CANDIDATE_CHANGED / PLAN_STALE | 不复用旧操作改用途；重新生成明确候选，以新 operation_id 计划并重新确认 |
| BASELINE_CHANGED / REVIEW_STALE | 保留双方修改，检查相关差异后重新计划、物化和真人确认；不要直接改摘要或批准记录 |
| HUMAN_ACTION_REQUIRED / CONFIRMATION_MISMATCH / REVIEW_NOT_ACCEPTED | 保持待确认；由真人在正确终端核对当前视图，不能让 Agent、输入重定向或伪造 JSON 补批准 |
| INVALID_PARTIAL_VIEW | 核对非空严格子集、同一 Card/scope、被保留 Claim 与来源；需要实质修订则走新计划 |
| 写锁冲突、ID 冲突、apply 中断或工具错误 | 停止并保留 `.build/<operation_id>/`、`logs/operations/<operation_id>/`、持久证据与人工记录；查清是否已写及恢复状态，不手工删锁、覆盖他人文件或继续索引发布 |

同一操作的安全重试须先确认其输入和基线没有改变；不能把重试当作绕过冲突的办法。完整中断恢复流程属于 T08；遇到当前版本不能恢复的事务，保留现场并报告，不声明已完整落位。
