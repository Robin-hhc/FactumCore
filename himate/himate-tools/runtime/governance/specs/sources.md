# 来源身份、扫描和回源

## 文件身份与版本

来源登记保存doc/code文件身份、实际仓库及路径。卡头通过doc_ref/code_ref引用来源ID和具体定位，同一文件可被多张卡采用。SHA-256表示本次读取内容，ID不因普通内容修改而改变。

普通 ingest scan 读取仍存在的原文档计算摘要，与上次成功处理的版本比较。新增、修改及未覆盖的文档范围进入文档入库。原文档删除及代码引用变化由巡检选择为已有卡维护。路径读取失败报告实际错误。

原件只读。P1 固定本次原件字节，P2—P4 复用它及其材料。PDF、DOCX、XLSX 可分轮评估并继续使用同一来源 ID。P5 用 P1 的摘要登记本批范围或整份完成。

独立 ingest 每批成功后返回 P1，在本次原始范围内继续扫描，直到该范围返回 unchanged；未指定来源时不把上一批 source_id 当成后续筛选条件。指定文件、目录或来源 ID 时保持原始范围，沿用解析配置、阅读预算及命令前缀，reprocess 仅首次使用。巡检中的 P1 仅采用 L2 选定的来源，所选来源无待办时返回 L2 重新调度。失败及暂缓不等于扫描无待办。

巡检发现待入库的 raw 文档时，`patrol plan` 返回 `needs_ingest` 和 `next_file.task_type=document_ingest`。代码关联卡复核和原文档删除返回 `needs_maintenance`、`task_type=card_maintenance`。`next_file.change` 区分首次缺基线、变更、删除和引用失效。未被正式卡引用的代码不产生入库任务。

维护依次调用 `knowledge maintain prepare --source <source_id> --json`、`maintain check` 和 `maintain commit`。L3 固定当前来源版本及正式反向引用决定的卡 ID、路径和原卡摘要，交接原卡与当前、可信历史材料。L4 修订相关引用、正文结论或生命周期，L5 独立审阅，L6 发布。CLI 检查和发布再次核对固定输入及当前正式卡，拒绝新卡、无关卡、移动和物理删除。候选为空仍需实际复核，发布时以 reason 说明零修改依据。

`source.reference_review` 独立记录 `source_sha256`、`exists`、`reviewed_at` 和 `source_commit`。旧 `processed_hash` 仅表示来源入库处理事实，不自动充当代码关联卡复核基线。缺少 reference_review 的已引用代码须先核验既有卡。维护回执的 `maintenance_complete`、`reviewed_card_ids` 和 `reviewed_hash` 表达关联卡复核，不返回整份代码入库完成语义。原文档删除维护记录缺失事实，保留既有文档入库进度及历史依据。

来源删除时 `source_sha256` 为 null、`exists` 为 false，已有真实版本的摘要保留为 `last_present_sha256`，供保留的历史引用按实际 Git 字节恢复。它不表示当前文件仍存在，不将旧处理版本自动视为复核基线。代码历史读取优先采用已复核版本或最后存在版本的摘要，必要旧字节不可恢复时仍报告缺口。

删除维护后的文档重新出现时，即使字节摘要与旧入库版本相同，也进入文档 P 链重新评估。首次成功发布的完整或部分文档处理清理过期的删除复核事实，长文随后按新一轮进度续办。重新入库后再次删除仍进入维护。代码的复核状态不随文档处理清理。

维护的当前、历史原件及解码文本和位置候选按固定材料引用与摘要核对。更改阅读文本、交接指针或固定材料字节须重新备料。删除来源的空候选也逐项核验保留引用的真实历史字节或有效快照，缺失证据不能仅凭零改理由登记为维护成功。

原卡内容、路径或来源在备料后改变时重新备料，已写入且与原批候选完全相同的文件可沿同批重试。来源读取、位置检查和事务实现与文档入库共享。旧 `ingest scan --source <code_id>` 无论是否携带 code_review，都准备同样受限的维护任务，遗漏标记不能放开新卡权限。

有按实际 hash 恢复的可信旧源码、原引用匹配且当前符号唯一时，L3 通过 `location_candidates_ref` 提供旧、新引用位置及片段是否相同的事实。候选始终标为 `requires_context_review`。L4 结合相关上下文确认行为和条件不变后才采用仅位置修订，所有候选仍经 L5。没有可信旧版、符号不唯一或仅片段相同都不构成自动语义结论。

## 完整转换与分轮阅读

P1 为 PDF、DOCX 和 XLSX 交付完整 `document.md`、结构 JSON 和原件位置索引。Markdown 在对应位置引用本地图像，适用的离线 OCR 附在对应图下。PDF 保留物理页边界。图像或原件资料无法取得时，P1 返回 `blocked` 和实际诊断。

`task.document_review` 从最早未评估单元给出候选范围、`packet_ref`、`index_ref` 和 `markdown_ref`。候选是全文 Markdown 的连续切片。图像路径以全文 Markdown 所在目录为准。正文统一最多 76,000 UTF-8 字节，为字节级 tokenizer 的 80k token 留余量。超长单元可分割，`review_text_budget` 的较小值按可用单元收束。显式旧 PDF `review_page_budget` 可以继续限定候选页数。

P2 计划使用 `source_units: [[start, end]]`。起点等于 P1 首个候选单元，结束可以提前。本批为完整物理页的 PDF 可以兼容 `source_pages`。P4 对照原件摘要、全文稿、候选和计划范围校验，独立 reviewer 打开 Markdown 中影响结论的图像。

部分完成记录原件版本与 `reviewed_units`，并用 `review_sha256` 绑定阅读稿。整页一一对应的 PDF 可继续保存 `reviewed_pages`。SQLite 重建后从正式登记恢复。旧 PDF 的同版页覆盖可映射到新阅读单元。

P5 将已审且成功提交的范围合并到 `processing`，覆盖全文时登记 `processed_hash`。必要依据未齐时停在当前阶段。显式 reprocess 的首批从头开始，后续普通续办，首批成功前保留旧成功事实。

## 格式与外部目录

沿用已有文档提取适配器，文本行段、文档章节与PDF页码按原件格式解释。不支持的提取明确报告缺口，不执行原件。代码只从真实配置和明确登记路径读取，不由同名或模块标签推断实现。

Docling 生成结构及图像，MD/TXT 直接读取。三种格式在 `artifacts/ingest/parsed/` 使用可重建的完整缓存，绑定来源身份、原件摘要、解析配置与 OCR 模型。缓存命中时校验文件摘要。转换未完成的产物保留诊断入口，后续重试重新备料。其它格式继续使用本轮 `.build/materials/parsed`。

原生 PDF 内部按最多 200 页转换，合并后保留物理页。未配置 `max_pages` 时按实际物理页数准备。输入大小、转换时长和产物配额通过顶层 `parser` 显式配置。完整材料的默认产物配额为 1 GiB，包含 Markdown、结构、定位和图片。

PDF 原生位图通过 PDFium 按物理页和原件位置提取，保留定位并按实际像素去重。需要核对矢量图或位图匹配有歧义时，P1 在对应物理页保留原件渲染图。纯图片材料及 Office 嵌图使用预装 OCR。图像与结构保留各自的原件出处。

PDF 页侧独立、连续且等距排列的长数字列，在具有明确正文间隔且无结构或同列文字歧义时归为行号装饰。Markdown、text.txt、物理页文本和入库阅读包统一省略这些行号；结构 JSON 保留原文、self_ref 和 provenance，原元素仍可按绑定来源与解析配置的 locator 读取。正文编号、表格、代码、图示与不满足识别条件的数字保留，不使用纯数字行的全局删除规则。文字处理策略版本纳入 PDF profile，升级创建新缓存且不改累计评估进度。

P1 通过 `manifest-reference` 交接 manifest、摘要、身份、材料入口和缺口摘要。加载时校验来源、解析配置和产物字节。独立 `source extract` 返回完整描述符。

转换缺口摘要保留代码、重要程度、次数、定位样例和指向完整 manifest 的入口。`blocked` 由 P1 报告。

P2—P4 使用 task 固定的同版材料。Markdown 与图像是阅读入口，结构和定位供核对。依据丢失或摘要变化时重新备料并审阅。OCR 和模型读取均在本地运行。图片语义由 Agent 实际看图判断。

`source extract` 为已登记来源生成独立阅读目录 `artifacts/source-read/<read_id>/`。PDF 可指定 `page_range` 或 `page_start/page_end`，`page_preview: false` 时只取提取材料。用 `source release` 释放读取目录，未到期目录可用 `source renew` 续期。独立读取和入库各有自己的暂存及进度。

解析器升级或需要改进已有来源抽取时，以具体来源和 `reprocess: true` 显式开始一次入库，继续经过决策、成稿与独立审阅。单独生成阅读稿不表示重新完成知识入库。

代码默认UTF-8；GB18030来源通过source register请求的encoding字段明确登记。该文件属性随来源ID保存，P1备料、P4定位和历史文本提取复用同一编码；原字节和hash不转码，不用伪造历史snapshot解决新文件编码问题。重新登记编码不推进内容成功标记。

登记请求写入JSON文件，再运行 `knowledge source register --input FILE.json --json`：

```json
{"kind":"code","path":"main/<module>/<file>.c","encoding":"gb18030"}
```

示例路径须替换为实际文件。无 repo_id 时，path 相对代码工作区基准，即知识根按 code_root 开头的 ../ 向上定位的目录。默认 code_root 为 ../../main，对应路径 main/<module>/<file>.c。填写 repo_id 时，path 相对对应的已配置仓库。文档用 kind=doc，path 相对知识根且位于 docs-raw。编码字段只用于代码。采用返回的 source.id。

外部dbox沿用本机目录映射，私人绝对路径留在被忽略的local配置；当前映射不可读时说明实际缺口。目录映射不提供执行或发布权限，不自动下载网页资料。

## Git按需恢复

Git不参与日常scan判变。需要旧全文时，source resolve根据已登记文件和可用commit/hash读取实际历史；可选source_commit表示来源已存在的版本，不是知识卡将来的提交。

P1 将本批原件准备到 `.build/`，供后续编写和审阅。P5 发布知识卡并更新来源登记、处理摘要和索引，成功后清理本批暂存。普通引用通过来源 ID 和登记路径读取当前原件，摘要用于发现来源变化。显式提供快照、hash 或 commit 的历史读取继续按所指定的版本校验。

没有对应Git历史且没有保留副本时，hash无法还原旧内容。浅克隆、外部来源或未提交旧版本可能无法恢复；不能把最新内容冒充旧版。P2可基于本轮材料范围和旧卡继续判断，必要上下文按需补读，确实影响结论时明确暂缓。

## 定位

独立 `source extract` 的物理页预览按像素和字节预算逐页交付。达到预算时报告剩余范围，已生成页可直接读取。自动补看蒙版图与入库材料中的原件页图分属各自的读取产物。

`element` 身份绑定原件摘要、解析 profile 和页段，只可在对应固定材料中选取。解析策略升级后重新提取时，须从同版本原件重新取得元素定位。正式 PDF 卡优先引用原物理页或页段。

新引用格式见[卡片规范](cards.md#卡头与引用)。代码引用可以包含文件ID、真实符号和行段；函数插行和行为变化分别处理，导航定位成功不证明技术结论正确。

原source_id/snapshot_id/locator和已正式保留的旧证据继续读取，历史字节不重写或重签。旧来源恢复能力按其实际保存内容工作，但新任务不再生成冻结bundle、发布闭包或阶段凭据链。
