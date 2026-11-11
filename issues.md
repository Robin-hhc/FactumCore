# HiMate 知识库入库问题总结

已定位到根因：分段按页的设计确实存在，但只存在于“审阅材料切片”这一层，解析层始终是整本一次解析。下面说明具体阻塞点，供远端开发修复。

阻塞点：分段只切“审阅包”，不切“解析”
现有链路是两段：

解析层：prepare_pdf() 调 parse() 时不传 page_range（document_parser.py:249），整本 5956 页一次性解析成单个 bundle，然后才做 256MB 产物校验（document_parser.py:773）。所以整本必超限。
审阅层：_prepare_pdf_review() 才做分段——它从已经解析好的整本 bundle 里按 start/end 切出 pdf-review.md（ingest.py:329，切片函数 _pdf_packet 在 ingest.py:279）。分页覆盖记录 reviewed_pages/remaining_pages 也在这层（catalog.py:62）。
也就是说：按页累计覆盖的设计是真的，但它依赖“整本 bundle 已存在”这个前提。5956 页整本 bundle 424MB 撞上 256MB 硬上限，第一步就过不去，后面的分段逻辑根本没机会执行。

为什么必须问你
因为这不是配置问题，是契约层的硬限制，两条修法都动 governance：

parse() 本身支持 page_range（document_parser.py:701、:725），_docling 也支持（:626）——能力已经具备，只是 prepare_pdf 和 ingest scan 没把它接出来（ingest.py:460 调 prepare_pdf 时没传页范围）。
max_output_bytes 在 _options() 里被硬编码封顶 256MB（document_parser.py:82-83），传 1GB 会被 PARSE_OPTIONS_INVALID 直接拒掉。
所以要么改 prepare_pdf/scan 把页范围传下去（推荐，能力现成），要么放开产物上限。两者都改锁文件+契约，我不能自己拍。
