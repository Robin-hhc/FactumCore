# 来源登记和页面预览

下列命令使用已确认的 CLI 入口，带同一 `--knowledge-root`，工作目录为知识根。临时请求 JSON 可放在本轮暂存中。

需要新增来源时运行 `knowledge source register --input FILE.json --json`。文档示例 `{"kind":"doc","path":"docs-raw/example.md"}`，`path` 相对知识根。代码示例 `{"kind":"code","path":"main/<module>/<file>.c","encoding":"gb18030"}`，替换为已核实的实际路径。未给 `repo_id` 时，路径相对代码工作区基准（按 `code_root` 的前导 `../` 从知识根向上定位）。给了 `repo_id` 时，路径相对对应的已配置代码仓。编码只用于代码；缺省 UTF-8，核实为 GB18030 才显式设 `gb18030`。使用回执中的 `data.source.id`。

优先查看 task 固定 Markdown 内的图片和相邻 OCR。补看原页可用 `knowledge source extract --input FILE.json --json`，例如 `{"source_id":"doc-example","page_range":[10,12]}`。按像素或字节预算交付实际生成页，回执提示剩余范围。返回的 `source_sha256` 与 `task.source.hash` 一致时可用 `role: page_preview`；如今原件改版时回看 task 固定的 `source.original_ref`。

用完以 `{"read_id":"实际返回的ID"}` 调用 `knowledge source release --input FILE.json --json`，释放本次独立阅读目录。
