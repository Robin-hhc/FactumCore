# 来源材料操作

## 材料输入

`prepare` 直接准备指定阅读材料，不先强制扫描。以下输入按实际任务选用：

| 选择方式 | 请求内容 |
|---|---|
| 固定扫描清单 | `scan_ref`，可选 `unit_ids`；省略单元选择时采用非 `unchanged` 单元 |
| 明确 raw 目标 | `targets` 中提供 `source_path`，可附 `source_id/attachments/version/context_ref/expected_fingerprint` |
| 明确代码目标 | `targets` 中提供 `kind:"code"`、`repo_id`、`relative_path`，可附 `source_id/text_encoding/version/context_ref` |
| 明确卡片、主题或代码包 | `candidate_card_ids`、`topics`、`code_bundle_refs`；代码包必须是本次授权范围内的当前代码 |

`source_path` 相对 K；代码 `repo_id` 使用项目发现返回的实际模块身份，`relative_path` 相对该模块。`code_bundle_refs` 可为引用字符串或 `{bundle_ref,bundle_digest}`。使用本次返回的身份和引用，不猜机器路径或另建来源登记。

输出 `prepared` 包含 `material_ref/material_digest`、`bundle_ref`、适用的 `scan_ref` 和 `gaps`。材料保存新旧原文、完整候选旧卡、定位、采用版本和缺口；候选关联只是阅读线索，由 P2 决定是否修改。独立目标不伪造全库扫描、变化分类或完整性。

## 补料与返工

| 当前状态 | 调用方式 |
|---|---|
| 语义计划及候选尚未冻结 | `prepare` 可在当前操作用 `existing_material_ref` 和明确补充目标保存新材料版本 |
| 已有候选 view，明确返回补料 | 新 `operation_id`，传 `existing_material_ref`、实际 `previous_view_ref`、非空 `revision_reason` 和补充目标 |
| P2计划已冻结，但P3尚无view | 保留实际停点；不能承诺同操作换材料后可重写计划，也不能编造前序view开启返工 |

已有候选的补料沿用它绑定的原扫描及处理单元身份，保留旧工件。新材料必须继续显式传给后续计划与稿件，不能重新采用旧材料引用冒充补料结果。采用来源、旧卡、代码、配置或规则已经变化时，按 `SOURCE_CHANGED` 等诊断刷新实际输入；不沿失效清单假称已补齐。

原失败的确定重试与新一轮观察分开处理。材料仍有缺口时如实交作者，不能为继续流程伪造原文、摘要或通过声明。

## 巡检备料

使用 patrol 返回的 `source_request` 调用 `prepare`。保留变化 raw、待修卡来源和当前代码目标的明确并集；纯代码修订可以有 `unit_ids: []`，不能省略这个选择而扩成默认范围。

仅请求显式启用时采用 `tolerate_source_errors` 或 `collect_local_attachments`。前者保留不可读／不支持材料的逐项欠账，不能吞掉指纹或配置漂移；后者枚举已落地 Markdown 的安全本地附件，不获取远端内容或宣称识别图片语义。巡检借用的固定库存不属于本次 P6 可清理暂存。

## 确切来源操作

### capture：独立捕获

raw 请求使用 `source_path/source_id`；代码请求使用 `kind:"code"/repo_id/relative_path/source_id`。可选 `version` 仅记录明确提供的版本线索，缺失保持未知。

支持非空 UTF-8 MD/TXT、具有文字层的 PDF、DOCX 段落和表格；图片等未解释内容保留限制。代码的 `text_encoding` 可明确为 `utf-8` 或 `gb18030`，不猜编码、不转写原文件。代码模块按根 `config.yml` 的真实映射授权，标签或符号定位不能证明宏、构建或当前产品适用性。

### resolve 与 resolve-source：恢复原版

- `resolve`：给出确切 `bundle_ref`。
- `resolve-source`：给出 `source_ref:{evidence_ref,source_id,snapshot_id,locator}`，可附确切 `bundle_ref`；未提供包时读取正式登记的指定快照。

使用返回的 `original_ref`、`text`、定位和限制。`current_source_matches` 单独说明当前授权文件是否仍匹配，可能为 true、false 或 null；历史恢复成功不证明当前适用。

CLI 可从固定保留对象、确切本地 Git 对象或登记路径的匹配字节恢复原版，并核对提取与定位。缺旧版就保留缺口，不拿新版、同名文件或其他执行目录顶替。MD/TXT/文本代码按行，PDF 按页，DOCX 按段落／表格行解释；不透明附件不产生解释文本，字节定位也不冒充语义证据。

## 原件与输出边界

原件只读，材料与请求／响应使用本次 K 下的操作暂存。dbox 是逻辑来源目录，私人映射只留执行端；附件不得越出实际来源根或跟随链接。需要旧规则、旧版本或来源恢复时只采用明确引用，不搜索“最近一次”私有执行。

已有 `sources[].code_ref` 随旧材料保留，新代码引用由 P3 作者依据实际源码填写。此处不替作者判断 Claim，不运行整库质量检查，也不写正式卡、来源锁、处理记录或索引。
