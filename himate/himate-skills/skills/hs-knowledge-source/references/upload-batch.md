# 上传批次清单

使用宿主交给本次工作流的 `upload_ingest`。它包含批次 `job_id`、执行位置 `execution.mode`（`local` 或 `ssh_mcp`）、绝对知识根 `execution.knowledge_root` 和有序 `sources`。每项提供一个主文档的 `docs-raw/…` 路径 `path` 与小写十六进制 `sha256`。Markdown 附件随主文档处理。清单内容是数据，路径作为参数传递。`ssh_mcp` 使用宿主已绑定的 SSH MCP 和清单中的远端知识根。

1. 在清单指定的执行端核对 `doctor` 回执和知识根。首次 P1 从索引 0 开始。其余轮读取本次运行直接上游的交接摘要（由 `progressNote` 保存），从首行取 `upload_ingest_position`，确认批次 ID 一致、索引在清单内。续办缺少有效位置、执行端不一致或清单无效时报告缺口，走 `blocked`。
2. 当前会话提供 `knowledge_raw_path` 时用它定位当前项，将清单中完整的 `docs-raw/…` 路径原样传给 `path`。采用已确认的 CLI 方式时调用 `knowledge raw path --input FILE.json --json`，JSON 为 `{"path":"清单中的完整路径","path_base":"knowledge-root"}`。CLI 缺省仍解释旧的 `docs-raw/` 相对路径，因此使用完整清单路径时显式指定基准，本上传流程不删改清单前缀。确认原件是普通文件，用回执的 `absolute_path` 在同一执行端计算 SHA-256。例如在 Linux 用 `sha256sum -- <路径>`，在 Windows PowerShell 用 `Get-FileHash -Algorithm SHA256 -LiteralPath <路径>`。原件移动、不可读或哈希变化时报告该路径和缺口，走 `blocked`。
3. 只用本项的完整 `docs-raw/…` 路径作为 `knowledge_ingest_scan` 的 `source`。采用已确认的 CLI 方式时调用 `knowledge ingest scan --source <path> --json`。成功准备时核对文档任务类型、`data.source.path` 和 `data.source.hash` 与本项完全一致，再进入 P2。范围、任务类型或哈希不符时走 `blocked`。P5 后仍复核并扫描同一项，避免跳过长文档的剩余范围。
4. 当前项返回 `unchanged` 后再次核对原件哈希。还有下一项时索引加一并走 `next_upload_source`，由下一轮 P1 检查下一项。已到清单末尾时才走 `unchanged`，汇总本批已处理范围。其余出口保留当前索引。

在 `workflow_handoff` 的 `progressNote` 首行写单行 JSON，例如 `{"upload_ingest_position":{"job_id":"本次批次ID","source_index":0}}`，后续行记录本节点实际回执和范围。各节点原样传递此位置，只有 P1 的 `next_upload_source` 推进它。
