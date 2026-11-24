# 来源操作

本节点提供 `knowledge_source_register` 时使用它，独立部署用 `knowledge source register --input FILE.json --json`。请求包含 `kind`（doc/code）、`path` 和需要时的 `repo_id`；代码路径按实际配置解析。采用回执返回的来源 ID。

代码默认按 UTF-8 读取；实际为 GB18030 时在登记请求中填写 `"encoding":"gb18030"`。编码由来源登记保存，原字节不转码；不要伪造旧快照声明编码。

用 `knowledge_source_list` 查询来源及关联，独立部署用 `knowledge source list --input QUERY.json --json`。`processing` 给出同版原件已评估且完成登记的 `reviewed_units`，按完整物理页登记的 PDF 使用 `reviewed_pages`。整份完成以当前原件和成功 hash 一致为准。

用 `knowledge_source_resolve` 按来源 ID 和已有版本参数回源，独立部署用 `knowledge source resolve --input SOURCE.json --json`。恢复只限可用历史中的实际版本；没有提交且没有保存的旧内容无法凭 hash 找回。缺旧版时将缺口交 P2。

P1 返回的是本次副本和关联卡入口，不要求一次加载全部正文。Git 仅用于按需回看历史，不参与日常变化判定。

PDF、DOCX、XLSX 的 `task.source.parsed` 用紧凑描述符交接全文 Markdown、结构、定位和固定 manifest。图片、OCR 状态和完整缺口见 manifest。`source extract` 返回独立阅读目录的完整描述符。

三种格式的完整材料缓存按来源身份、原件版本、解析配置和本地 OCR 模型校验复用。后续节点使用 task 指向的同版材料，正式进度由来源登记保存。

`task.document_review` 给出 `start_unit`、`end_unit`、`total_units`、`reviewed_units`、`remaining_units`、`text_bytes`、`packet_ref`、`index_ref` 与 `markdown_ref`。先看索引，再读选定的 Markdown 范围。图片路径从完整 Markdown 的目录解析。完整物理页可映射为 PDF 单元，超长页可以占多个单元。

`blocked` 的 `data.gaps` 提供转换错误及 manifest 明细入口。P1 需要修复后再交接。P2/P4 对选定范围内的图示打开 Markdown 中的本地图片，结合相邻 OCR 核对。

候选正文统一最多 76,000 UTF-8 字节，为 80k token 留出余量。历史 `review_text_budget` 可以缩小候选，按完整单元交付，超过上限时以统一上限为准。显式 `review_page_budget` 只用于兼容早期 PDF 请求。解析配额写在顶层 `parser`。

P2 自主缩短结束单元，并在计划写 `source_units`。只有实际选定、经过评估、P4 和 P5 的范围进入覆盖。

回源用 `knowledge_source_extract`，按需指定 PDF 物理页范围。读取结束用返回的 `read_id` 调用 `knowledge_source_release`，较长读取先调用 `knowledge_source_renew`。独立部署用 CLI 的 `source extract/release/renew`。各读任务使用 `artifacts/source-read/<read_id>/`，与本轮 `.build` 独立。`source cleanup` 用于宿主回收过期且非转换中的产物。
