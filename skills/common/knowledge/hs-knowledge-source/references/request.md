# 来源请求与独立动作

## 通用调用

```text
python K/knowledge.py source --action ACTION --input REQUEST.json --json
```

K 是实际执行端的知识根；可显式传 `--knowledge-root K`、`--output RESPONSE.json`。请求使用本次 `operation_id`；当前规则锁默认加载，只有需要固定版本时才传 `--rules-digest`。动作由 CLI 参数选择，不在 JSON 中另写动作。

## 正常观察与备料

省略 `--action` 等同 `run`。

| 请求项 | 用途 |
|---|---|
| `source` | 可选 `string`，限定相对 K 的一个 raw 文件或目录 |
| `unit_ids` | 明确选择实际库存单元，不重新编造单元 |
| `candidate_card_ids`、`topics` | 明确修卡或找卡线索；主题不自行扩大扫描范围 |
| `targets`、`code_bundle_refs` | 明确需要的原文或当前代码材料，格式见[材料输入](materials.md#材料输入) |

默认扫描六类仓内 raw 和逻辑目录 `docs-raw/sources/dbox`，对照正式处理记录及维护限制。指定普通 raw 范围不依赖无关 dbox 配置。读取失败或扫描不完整不会被当作全部删除或无需更新。

`prepared` 返回实际扫描与材料引用；`unchanged` 只表示这次完整观察确无事项。空 `actionable_unit_ids` 不能单独证明无需处理，来源未变也可以有明确修卡任务。

### 重试与漂移

同一操作重试只采用该操作已保存的观察，范围保持不变；要采用别的库存或定向补料，调用 `prepare`。`FRESH_OBSERVATION_REQUIRED` 表示旧无变化观察不能代表现在，应新建操作重新观察。`REVISION_SOURCE_REQUIRED` 表示修卡目标缺少可匹配的实际来源，应补充明确来源或改用定向 `prepare`。

失败响应保留原诊断，`data.stopped_stage` 指明停在 `scan` 或 `prepare`。有 `needs_scan/affected_scope` 时区分 raw、卡片、代码、配置或规则的实际变化；不能盲目重扫、覆盖旧产物或把所有路径都传给 `source`。

## 独立动作

以下动作只在当前任务明确需要时使用。

### configure：配置 dbox

需要使用 dbox 且实际执行端尚未配置时调用。请求可提供 `path`，值为该执行端可读的原生绝对目录；省略 `path` 只检查原配置。

```json
{"operation_id":"configure-dbox","path":"ACTUAL_ABSOLUTE_DIRECTORY"}
```

把示例目录换成实际地址。配置固定保存在 `K/docs-raw/sources/dbox.local.yml`，包含 `schema_version: '1.0'` 和 `path`；私人文件不入库。CLI 核对目录和忽略保护后保存，同地址保留原字节。配置成功只证明根目录可用，不等于文档已扫描或入库。正常 `run` 不隐式配置或安装环境。

### scan：只观察

可传 `source` 限定范围，返回 `scanned`、`scan_ref`、摘要、范围和完整性，不准备材料。`new/changed/missing/unchanged/unfinished/read_failed` 是观察事实，作者仍需判断处理方式。

完整的可读空范围有效；明确指定一个不存在且没有正式删除历史的文件会返回 `RAW_SCOPE_NOT_FOUND`。只有完整扫描才能据“未见”推断缺失。`prior_record_refs` 仅供明确的记录恢复用途，普通调用读取正式记录。

### capture、resolve、resolve-source：确切来源

捕获或恢复原文时读[确切来源操作](materials.md#确切来源操作)。正常 `run/prepare` 已准备的材料不再重复捕获。

### status：观察已有执行事实

需要查某次执行时提供 `target_operation_id`；只读取该操作及其确切引用。已发布操作可从正式 publication 读取，旧暂存已清理不等于发布失败。省略目标是明确的全局历史概览，可能返回 `catalog_gaps`。

读取 `facts/stage_status/completion` 与真实缺口。保存的完成事实不代表当前索引健康，`cleanup_pending` 也不抹去已发布内容。此动作不恢复事务、重建索引或改变文件；需要这些操作时交对应维护任务处理。
