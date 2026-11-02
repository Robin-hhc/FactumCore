# 来源操作

`knowledge source register --input FILE.json --json` 登记实际来源文件。请求包含 `kind`（doc/code）、`path` 和需要时的仓库身份；代码路径按实际配置解析。ID 由 CLI 返回，不根据标题猜测。

代码默认按 UTF-8 读取；实际为 GB18030 时在登记请求中填写 `"encoding":"gb18030"`。编码由来源登记保存，原字节不转码；不要伪造旧快照声明编码。

`knowledge source list --input QUERY.json --json` 查询来源或关联：按来源 ID 查卡、按卡 ID 查所有来源，或按 kind 列出已引用文件。使用返回的真实路径与 ID。来源有 `processing` 时，返回其绑定的 `source_sha256` 和累计 `reviewed_pages`；这表示该版本已有部分范围完成评估和发布，不是工具打开过的页面轨迹。没有 processing 也不自动表示完成，仍须核对整文成功 hash 与当前原件版本。

`knowledge source resolve --input SOURCE.json --json` 按来源 ID 和需要的 Git 版本读取原文。恢复只限可用历史中的实际版本；没有提交且没有保存的旧内容无法凭 hash 找回。缺旧版时将缺口交 P2，不冒充已读。

P1 返回的是本次副本和关联卡入口，不要求一次加载全部正文。Git 仅用于按需回看历史，不参与日常变化判定。

`task.source.parsed` 交付固定摘要的文字、Markdown、结构 JSON、原文定位及图片。PDF 缓存在 `artifacts/ingest/parsed/<cache-key>-<generation>/`，按来源身份、原件 hash 和实际解析配置校验复用；缺失或损坏时可重新生成，不用缓存保存唯一处理进度。非 PDF 产物仍在 `.build/materials/parsed`，P5 成功后随本轮暂存清理。后续节点使用 task 指向的同一份材料，不能重转后替换已经审阅的依据。

PDF 的 `task.pdf_review` 返回 `total_pages`、`reviewed_pages`、`remaining_pages`、`start_page`、`end_page`、`page_budget`、`text_budget`、`text_units`、`packet_ref`、`page_index_ref`。起点是最早未评估页，结束页是候选上限；`page_budget: null` 表示不限制页数，`text_units` 是实际候选字量。`.build/materials/pdf-review.md` 提供逐页文字，配套 JSON 逐页提供 `text_units`、`image_count`、`table_count`、物理页定位及图片/结构入口，缺页与解析缺口明确报告。先看索引，再按需分段读取；不要求一次加载候选全文。缺失提取不能当作已确认空白页。

scan JSON 的 `review_text_budget` 默认 400000 等效字符：ASCII 字符计 1，其它 Unicode 字符计 4，约为英文 40 万字符或中文 10 万字，不是精确 token 数。P1 整页纳入，达到或跨过阈值后停止，不截断页，也不因单页过长拒绝。`review_page_budget` 默认不设，仅显式传入 1–1000 的整数时限制页数。

80k token 是 Agent 安排上下文的软目标，脚本不检查。P2 可结合上下文、图表、条款和产卡量，自主缩短实际结束页；计划 `source_pages` 从 task 起点开始且不超过候选结束页。只有实际选定范围经评估、P4 和 P5 后才记覆盖；补读前文或卡片证据引用不自动计入。

独立回源用 `source extract`，按需指定 PDF 页范围；读取结束用返回的 read_id 执行 `source release`，较长读取先 `source renew`。各读任务使用 `artifacts/source-read/<read_id>/`，不影响当前 `.build` 或其他查询。`source cleanup` 有界回收过期且非转换中的产物。
