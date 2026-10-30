# 代码依据核验

仅在代码／混合稿或明确的代码依据检查任务中读取。纯文档使用内容审阅；无需虚构代码链接或编译材料。

## P4 的代码输入

在 `review` 的 `code_review` 对象中提供 `context_ref` 和 `semantic_report_ref`。本轮 `operation_id` 与确切 `view_ref` 由 P4 传入。代码／混合稿核本次代码门禁卡，同时绑定完整候选。

`context_ref` 采用 P1 材料绑定的项目配置、入口和实际代码文件清单；E0 discovery 不能冒充完整代码上下文。核实际配置、采用文件 SHA-256、规则及工具身份，不以自动生成代替内容复核。模块工作区按配置范围和文件指纹核验，版本或 Git 身份未知不妨碍有依据的静态检查。

## 逐 Claim 技术判断

`semantic_report_ref` 指向 `semantic_review` 记录，含 `schema_version:"2.0"` 和 `payload`。payload 保留 `view_digest`、`context_digest`、`mode`、`issued_at`、`findings` 及 `claims`。

外层还须有 `record_kind:"semantic_review"`。P4 的 `mode` 为 `local`，独立 `code-recheck` 为 `merge`；`issued_at` 是实际 Unix 秒数（整数或小数），不传日期字符串。`findings` 明确列出实际问题，仍有问题时交回修订。

每个 Claim 写 `card_id`、`claim_id`、`status`、非空 `reason` 和绑定实际快照、定位、SHA-256 的 `evidence`；空问题列表不能替代具体理由和依据。

`evidence` 为非空对象数组，每项含实际 `source_id/snapshot_id/locator/sha256`；逐一覆盖该 Claim 采用的全部来源，`locator` 沿用卡中原对象，`sha256` 是原件字节摘要。当前代码已经漂移时另提供绑定实际上下文的 `checked_snapshot`；不能改旧快照或补造当前依据。

| 声明的要求 | 需要什么依据 |
|---|---|
| `semantic-support` | 真实静态源码、配置与条件推理，不强制编译 |
| `build-support` | 确切 Target／构建身份及已固定的构建产物 |
| `runtime-support` | 实际运行观察及已固定的运行证据；测量结论需要此项 |

构建／运行项还要在 Claim 的 `verification_evidence` 中列 `requirement`、`path`、`sha256`，对应上下文 `build_evidence` 的实际文件。缺必需输入保持未完成，检查命令不启动构建。未证实的产品条件不从芯片／模块标签推断；无 Target 时仅支持相应 historical／guidance、unknown 且无 context 分组的源码结论。

活动卡代码 Claim 逐项 `supported`；最终退役卡可用 `retired`，说明实际退役理由及替代去向并核原始证据，不要求旧断言仍被当前代码支持。

## 符号定位与语义分开

本次独立代码核验读 `code_review.check_status` 及其真实检查记录。顶层 `code_check_status` 只描述固定检查中 current Claim 的代码 checkout 分支；全为 guidance 时可为 `not_applicable`，不表示独立代码审阅没有执行。

每个活动卡的 code 来源均需 `sources[].code_ref`，包括未被 Claim 采用的来源。缺失报 `CODE_REF_REQUIRED`；supported 写法以 K 的 `governance/specs/cards.md` 为准，不用 file/range 兜底。

实际内容是否遗漏必要代码入口由 reviewer 判断。`resolved` 仅表示符号可定位；missing／ambiguous／unavailable 按实际结果保留，不能猜宏分支，也不能替代来源字节、Claim 语义及构建条件核验。历史恢复与 deprecated 卡沿用既有四字段来源兼容。

## 独立动作

| 动作 | 输入与用途 |
|---|---|
| `code-check` | `operation_id`、`view_ref`、`context_ref`、`semantic_report_ref`，核本次实际代码依据 |
| `code-recheck` | 对应当前代码材料与报告，复查当前依据；不执行合入 |
| `verify-evidence` | 原操作 `operation_id`、确切 `view_ref`、`proof_ref` 及 `purpose`（current 或 historical）；分别复查当前字节或固定旧证据 |

独立动作使用 `knowledge lint --action <动作>`，只完成所选检查，不表示完整 P4、真实 CI 或产品运行验收。旧报告保持原字节，不补签或改历史身份。
