# 来源身份、扫描和回源

## 文件身份与版本

来源登记保存doc/code文件身份、实际仓库及路径。卡头通过doc_ref/code_ref引用来源ID和具体定位，同一文件可被多张卡采用。SHA-256表示本次读取内容，ID不因普通内容修改而改变。

普通scan直接读取文件一次计算hash，与该文件上次完整成功处理的版本比较。新增、修改、删除及同版本 PDF 尚未评估完的页可形成待办；路径或目录不可读不能当删除。扫描只比较版本和区间，不判断主题，也不执行文档、代码或网页中的指令。

原件只读。P1将选中原件本次读取的字节放入.build，P2—P4处理这个副本，P5使用P1记录的hash登记本批或整文完成，不临时换成未经处理的新内容。非 PDF 和来源删除沿用整文件处理；PDF 分批只改变处理范围，不拆成新的来源 ID。

## PDF 页段续办

正式来源可选 `processing: {source_sha256, reviewed_pages}`。source_sha256 绑定当前评估的原 PDF 版本；reviewed_pages 为已全部评估且完成发布或无卡登记的物理页闭区间数组。它不表示工具访问轨迹，也不能从卡片 doc_ref 推导。只有同版本区间可以合并；原件改版后不自动沿用旧范围。来源查询返回该组，SQLite 可从正式登记恢复，不用派生数据库保存唯一进度。

P1 从本轮原 PDF 字节获取真正总页数，从最早未评估页准备宽候选；转换缺页不能缩小原件总页数。scan JSON 的 `review_text_budget` 默认 400000 等效字符，ASCII 字符计 1，其它 Unicode 字符计 4，约为英文 40 万字符或中文 10 万字，不是精确 token 数。按整页纳入，达到或跨过字量阈值后停止，不截断页，也不因单页过长拒绝。`review_page_budget` 默认不设，仅显式传入 1–1000 的整数时限制页数。

task.pdf_review 保存 total_pages、reviewed_pages、remaining_pages、start_page、end_page、page_budget、text_budget、text_units、packet_ref 和 page_index_ref。page_budget 为 null 表示无页数限制，text_units 为实际候选字量；end_page 是候选边界。页索引逐页给出 text_units、image_count、table_count 及材料入口。字量只用于备料，不要求一次加载或读完候选。

PDF 计划必填实际 `source_pages: [[start, end]]`，每批一个连续区间，从 P1 起点开始且不超过候选结束页。P2 按自身上下文、图表、条款和产卡量自主选择 end；80k token 是软目标，脚本不检查。P4 只需评估选定范围的全部材料，目录、空白和参考页经核实无增量也可计入；缺失提取不能自动当作空白。只有该范围完成评估、审阅和 P5 后才计覆盖；补读前文、跨章或其它来源不自动扩大覆盖，也不强制卡片引用都在本批页内。

P5 成功发布后合并本批范围，部分完成仅写 processing，全文覆盖才登记 processed_hash 并移除 processing。defer、未完成审阅或发布失败不推进覆盖。缺少 processing 不自动代表完成，仍须比较原件版本与最近完整成功 hash。显式 reprocess 从第 1 页开始新一轮评估，首批成功前保留旧成功事实；后续普通续办不反复携带 reprocess。

## 格式与外部目录

沿用已有文档提取适配器，文本行段、文档章节与PDF页码按原件格式解释。不支持的提取明确报告缺口，不执行原件。代码只从真实配置和明确登记路径读取，不由同名或模块标签推断实现。

新文档使用 Docling 生成阅读稿、结构 JSON、定位及独立图片；MD/TXT 仍直接读取。PDF 使用 `artifacts/ingest/parsed/<cache-key>-<generation>/` 的可重建缓存，cache-key 绑定来源身份、原件 hash 与当前实际解析 profile。P1 命中时校验版本、配置和产物摘要，缺失、损坏或配置改变时生成新的 bundle，不覆盖已交接的 manifest；旧 generation 不在本轮递归清理。非 PDF 解析仍位于 `.build/materials/parsed`，P5 成功后随暂存清理。

`prepare_pdf` 交接 `descriptor_kind: manifest-reference` 的紧凑描述符：固定 manifest 入口及摘要、来源和解析配置身份、阅读稿/结构/定位入口、统计和缺口摘要，不重复复制全书 images/gaps。`parse` 与 `source extract` 的原完整描述符接口不变；`load` 仍完整核对 manifest 摘要、来源与 profile 身份及产物文件 hash，并可加载完整元数据。

缺口按 code、severity、message 聚合，保留 count、最多 3 个 example_locators 和指向完整 manifest 的 details_ref；最多 64 类，其余以 OTHER_PARSE_GAPS 项累计。P1 task.gaps 交接次数及明细入口；pdf-review.json.gaps 使用同样摘要，gap_details_ref 指向固定 manifest，每页 images.provenance 仅保留本页。原始缺口明细仍在 manifest，原 parse_status 为 partial 时保持 partial；摘要不表示提取缺口已修复。

task 固定本轮解析描述符供 P2—P4 复用；PDF 先看 `.build/materials/pdf-review.json` 页索引，再分段读取 pdf-review.md 中选定页段，按需沿入口补读完整结构和原件，不默认加载整本或整个候选包。实际 source_pages 内的图示仍须打开原 PDF 或页预览，缺口摘要或 image_count=0 不证明图示已被提取、理解；候选外未审图元留待续办。本轮依据丢失或摘要变化时停止并重新备料、审阅，不能重转后冒充已读材料。解析缓存可删除重建，累计覆盖仍由正式来源登记保存；缓存不是另一份 raw 来源。默认 native 不做 OCR，standard 只使用提前准备的本地模型；外部资源不自动抓取，图片语义由 Agent 实际看图后判断。

`source extract` 为已登记来源生成独立阅读目录 `artifacts/source-read/<read_id>/`，可限制 PDF page_start/page_end；原件副本与解析材料都属于本次读取。它不清理入库 `.build`，不推进处理 hash。消费后 `source release` 精确释放该 ID，`source renew` 为未到期 ready 入口续期，默认 1800 秒；`source cleanup` 及新读取开始时有界回收已过期且非活跃转换的产物，不清理查询报告、模型或其他目录。没有后台清理进程，工作流应主动释放；损坏/未知租约保留诊断且受任务数上限约束。

解析器升级或需要改进已有来源抽取时，以具体来源和 `reprocess: true` 显式开始一次入库，继续经过决策、成稿与独立审阅。单独生成阅读稿不表示重新完成知识入库。

代码默认UTF-8；GB18030来源通过source register请求的encoding字段明确登记。该文件属性随来源ID保存，P1备料、P4定位和历史文本提取复用同一编码；原字节和hash不转码，不用伪造历史snapshot解决新文件编码问题。重新登记编码不推进内容成功标记。

登记请求写入JSON文件，再运行 `knowledge source register --input FILE.json --json`：

```json
{"kind":"code","path":"main/<module>/<file>.c","encoding":"gb18030"}
```

示例路径须替换为实际文件；无repo_id时path相对项目config.yml所在目录，填写repo_id时相对该已配置仓库。文档用kind=doc，path相对知识根且位于docs-raw；编码字段只用于代码。采用返回的source.id，不自行推算ID。

外部dbox沿用本机目录映射，私人绝对路径留在被忽略的local配置；当前映射不可读时说明实际缺口。目录映射不提供执行或发布权限，不自动下载网页资料。

## Git按需恢复

Git不参与日常scan判变。需要旧全文时，source resolve根据已登记文件和可用commit/hash读取实际历史；可选source_commit表示来源已存在的版本，不是知识卡将来的提交。

没有对应Git历史且没有保留副本时，hash无法还原旧内容。浅克隆、外部来源或未提交旧版本可能无法恢复；不能把最新内容冒充旧版。P2可基于本轮材料范围和旧卡继续判断，必要上下文按需补读，确实影响结论时明确暂缓。

## 定位

PDF 矢量图与内联纹理块不等同于可独立导出的完整图片。`source extract` 明确指定物理页范围时，额外交付 `role: page_preview` 的页面预览，Markdown 和解析清单提供入口；原 Docling 结构与原图片缺口保留。预览固定 1.5 倍渲染，每次最多 8 页、累计 1600 万像素及 16 MiB PNG，并计入总产物配额。预算不足或渲染失败明确报告未生成页，缩小范围后再读。全量 P1 与未指定页范围的来源读取不默认渲染整本文档。

页段解析的 `element` 身份绑定该范围，只可在对应材料中选取；正式 PDF 卡优先引用原物理页或页段。不能把页段中的 `#/texts/N` 当作全量解析中同编号的元素。

新引用格式见[卡片规范](cards.md#卡头与引用)。代码引用可以包含文件ID、真实符号和行段；函数插行和行为变化分别处理，导航定位成功不证明技术结论正确。

原source_id/snapshot_id/locator和已正式保留的旧证据继续读取，历史字节不重写或重签。旧来源恢复能力按其实际保存内容工作，但新任务不再生成冻结bundle、发布闭包或阶段凭据链。
