# 面板 CLI 契约

OpenFlow 在文件所在主机调用已绑定领域的 `knowledge.py`。命令从 stdin 接收 JSON 对象，沿用知识 CLI 的结果封装。

```sh
printf '%s' '{"limit":20}' | python -B /absolute/knowledge/root/knowledge.py panel cards --input - --json
```

成功读取 `status: "ok"` 和 `data`。失败读取 `diagnostics[].code` 和 `message`。卡、来源、路径等 ID 相对已绑定知识根解释。

| 动作 | 请求 | `data` |
| --- | --- | --- |
| `panel overview` | `{view_revision?}` | `{view_revision,card_count,document_count,code_count,types,recent_cards}` |
| `panel cards` | `{view_revision?,query?,type?,tag?,cursor?,limit?}` | `{view_revision,items:[{id,title,type,tags,summary}],next_cursor}` |
| `panel search` | `{view_revision?,query,tags?,top_k?}` | `{view_revision,matches,truncated}`，候选沿用整卡检索字段和权重 |
| `panel read` | `{view_revision?,card_id}` | 完整读卡结果与 `view_revision` |
| `panel graph` | `{view_revision?,card_id,kinds?,cursor?,limit?}` | `{view_revision,nodes:[{id,title,kind,ref_id?}],edges:[{source,target,kind}],next_cursor}` |
| `panel raw-list` | `{path?,cursor?,limit?}` | `{path,items:[{name,path,kind,size}],next_cursor}` |
| `panel raw-path` | `{path}` | `{name,path,kind,size,absolute_path}`，供可信文件服务使用 |
| `panel raw-save` | `{path,staged_path,expected_size?,expected_sha256?}` | `{name,path,kind,size,sha256}` |

`overview` 的文档和代码数量分别去重统计被正式卡引用的来源。类型项为 `{type,count}`，最近卡片为 `{id,title,type}`，按文件更新时间取至多 10 张。类型由目录映射，旧 draft 不进入面板，其他旧卡仍可浏览。卡片列表按 ID 排序，查询可按正文词项、卡片类型和单个标签过滤。标题、摘要和标签只显示列表所需的短值，完整内容可用 `read` 取得。

图谱从指定卡读取一跳。节点类型是 `card`、`document`、`code`，`kinds` 筛选邻居类型。边类型是 `doc_ref`、`code_ref`、`card_link`、`related_to`。卡片 Markdown 正文中指向同一发布视图内其他卡的相对链接形成 `card_link`，每对卡按方向合并一条。同卡同来源的多处定位聚为一条边，旧卡显式声明的 `related_to` 保留方向。源 ID 与卡 ID 冲突时，源节点提供 `ref_id`，用于来源查询。图页最多 50 条边和 51 个节点，其他列表每页最多 100 项。默认每页 30 项。下一页使用原筛选条件、`view_revision` 和原样传回的 `next_cursor`，末页游标为 `null`。实时原件目录使用名称排序，原件增删会在之后的请求中反映。

## 正式知识版本

执行 `maintain reindex --json` 构建首个面板版本，包括空知识库。成功的 P5 和显式重建在现有 SQLite 写事务内发布新 `view_revision`。重建失败保留上次成功版本。面板查询直接读取发布表，返回轻量分页数据。绑定或维护流程遇到 `PANEL_VIEW_UNAVAILABLE` 时可执行一次重建。版本已换时，客户端收到 `PANEL_REVISION_MISMATCH` 后刷新；筛选不匹配的游标返回 `PANEL_CURSOR_INVALID`。P5 在发布成功后更新本机最新回执。回执写入失败时，P5 仍返回 `completed`，并在 `data.receipt_warning` 报告文件错误。自动化应使用本次命令返回的结果。

Agent 可用 `panel search` 获取候选与版本，将该版本传给 `panel read` 读取同一发布版本。`read --input - --json` 同样接受 `{card_id,view_revision}`。已有无版本的 `read`、`search` 与 `source list` 保持各自的查询语义。版本化详情通过 `card_links: [{target,card_id,anchor?}]` 给出可生成深链的相对链接。 `target` 含正文中的原始片段，`anchor` 是已核对的解码后锚点。导航、原件、外部链接、图片、代码示例和不存在的锚点不进入这个映射。`heading_anchors: [{anchor,line}]` 提供治理解析器支持的正文标题锚点，行号从 `body` 的第一行起算。客户端应按源行设置这些锚点。旧投影可在下一次发布或重建后补出这些字段。

P4 检查在本批暂存记录实际核对过的来源字节。P5 将这些引用和精确来源版本关联到现有来源登记，正式卡保持审阅时的字节。卡片关联摘要统一 CRLF/LF，原件 SHA-256 按原始字节计算。重建只使用已持久化的绑定。对同样的卡片和引用重新核对并发布时，关联更新为这次核对的版本，历史快照仍可按 ID 查询。

版本化引用的 `source_version` 为 `bound` 时提供 `snapshot_id` 和 `source_sha256`，客户端可用 `source resolve` 发送 `{source_id,snapshot_id,hash?}` 取得精确原件。固定字节可通过已登记 Git 对象、同 SHA-256 的原件或本机证据对象恢复。本机证据对象留在 Git 忽略的目录。干净检出保留绑定，缺少对应字节时返回来源不可用。旧引用没有固定版本时显示 `unknown`，界面可查看当前原件并省略旧定位。显式快照缺失或关联不明确时显示 `unavailable`，不以当前版本代替引用证据。

## 实时原件

`path` 相对 `docs-raw/`，空串表示目录根。目录项 `kind` 为 `directory` 时 `size` 为 `null`，普通文件为 `file`。目录浏览读取物理文件，可显示尚未登记的文件。链接、隐藏项和本机 dbox 映射配置不参与浏览。保存目标必须是已有普通目录下支持入库的文件名，原件投递限于仓内目录。

OpenFlow 先在服务端完整接收上传，再将可信的绝对暂存文件名传给 `raw-save`。浏览器只提供业务相对路径和字节，由宿主构造 `staged_path`。CLI 流式校验并写到目标目录的临时文件，同目录原子提交完整字节。目标已存在或与同目录的名称只差大小写时，返回 `RAW_TARGET_EXISTS`。文件大小或 hash 对不上返回 `RAW_STAGE_MISMATCH`。暂存文件由宿主清理，返回文件相对路径与 SHA-256 即可确认保存。原件注册及正式知识更新由之后的 CI 完成。

`raw-path` 返回已校验普通文件的真实路径，供可信服务按文件权限提供下载或预览。浏览器只接收相对引用和内容。找不到路径返回 `RAW_NOT_FOUND`。原件目录读取与投递不触发入库扫描、卡片更新或索引重建。
