# 来源登记和页面预览

下列命令使用已确认的 CLI 入口，带同一 `--knowledge-root`，工作目录为知识根。临时请求 JSON 可放在本轮暂存中。

需要新增来源时运行 `knowledge source register --input FILE.json --json`。文档示例 `{"kind":"doc","path":"docs-raw/example.md"}`，`path` 相对知识根。代码示例 `{"kind":"code","path":"main/<module>/<file>.c","encoding":"gb18030"}`，替换为已核实的实际路径。未给 `repo_id` 时，路径相对代码工作区基准（按 `code_root` 的前导 `../` 从知识根向上定位）。给了 `repo_id` 时，路径相对对应的已配置代码仓。编码只用于代码；缺省 UTF-8，核实为 GB18030 才显式设 `gb18030`。使用回执中的 `data.source.id`。

图表未完全提取时先使用 task 固定的原件或页图。补看原页可用 `knowledge source extract --input FILE.json --json`，例如 `{"source_id":"doc-example","page_start":10,"page_end":12}`。每次最多取 8 个物理页。命令读取当前已登记的文件，只有返回 `data.parsed.source_sha256` 与 `task.source.hash` 一致时，才能作为本轮同版证据。查看 `data.parsed` 中 `role: page_preview` 的原页图片，结合原文/OCR 判断。若当前版本变化，回看 task 固定的 `source.original_ref`；仍缺必要材料时交接缺口。

用完以 `{"read_id":"实际返回的ID"}` 调用 `knowledge source release --input FILE.json --json`，释放本次独立阅读目录。
