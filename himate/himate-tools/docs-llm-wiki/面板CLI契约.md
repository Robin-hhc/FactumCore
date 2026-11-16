# 面板 CLI 契约

OpenFlow 通过宿主的 `OPENFLOW_KNOWLEDGE_TOOLKIT_ROOT` 定位 `knowledge.py` 和 `tools/deploy/environment.py`。工具包目录使用绝对路径，并与已绑定的知识根分开。宿主按 `OPENFLOW_KNOWLEDGE_PYTHON` 指定的绝对路径选择 Python 3.10–3.12，未指定时从宿主机探测。面板操作直接使用该解释器运行 `knowledge.py`，显式传入已绑定的知识根。业务命令从 stdin 接收 JSON 对象，沿用知识 CLI 的结果封装。

```sh
printf '%s' '{"limit":20}' | python -B /absolute/tool/root/knowledge.py panel cards --knowledge-root /absolute/knowledge/root --input - --json
```

成功读取 `status: "ok"` 和 `data`。失败读取 `diagnostics[].code` 和 `message`。卡、来源、路径等 ID 相对已绑定知识根解释。

## 环境检查和安装

环境入口可在首次绑定前执行。`<Python> -B <工具包>/tools/deploy/environment.py check` 返回一行 JSON，包含 `status`、`tool_root`、`toolkit_version`、`python`、`python_version`、`dependencies`、`diagnostics` 和 `command`。`dependencies` 的每项包含 `name`、`expected`、`actual` 和 `status`（`ready`、`missing` 或 `mismatch`）。每条诊断包含 `code` 和 `message`。

| `status` | 含义 |
| --- | --- |
| `needs_install` | Python 依赖缺失或版本不符，优先处理依赖 |
| `needs_cli` | 依赖齐全，命令待注册、修复或启动验证失败 |
| `ready` | 依赖齐全，受管理的启动入口通过 `--help` 验证 |

检查只读。无法加载工具包或依赖清单时，返回非零退出码和 `status: "unavailable"` 的诊断。`command` 为 `null` 或 `{path,bin_dir,dispatcher,installed,path_registered,on_path,shadowed_by}`。`installed` 表示启动文件与所选工具及 Python 匹配，并符合默认目录的注册要求。`path_registered` 表示 Windows 当前账户的用户 `PATH` 已登记该目录。`on_path` 表示当前进程的 `PATH` 实际优先解析到该命令，`shadowed_by` 记录优先匹配到的其他命令。Linux 上 `ready` 可以与 `on_path: false` 同时出现。

`install` 以 JSON 行发出 `checking`、`installing`（需要 pip 时）、`registering`（需要注册时）和 `verifying`。它先复查依赖，再注册命令。成功以最终 `ready` 报告和退出码 0 结束。失败事件包含 `phase`、`code`、`message`、`diagnostics`，并以非零退出码结束。已装依赖会在下一次检查时复用，注册失败重试时可以跳过 pip。同名文件冲突为 `COMMAND_EXISTS`，默认目录的命令被 `PATH` 中更优先的入口遮挡为 `COMMAND_PATH_CONFLICT`。Windows 0.22.3 起按 `PATH` 和 `PATHEXT` 查找，单独存在于当前目录的工具包启动文件不会触发这个冲突。

OpenFlow 用 `POST /api/knowledge/environment/check` 检查，用 `POST /api/knowledge/environment/install` 开启后台安装，两者以 JSON `{}` 提交。用 `GET /api/knowledge/environment/install` 查询当前任务。宿主进程同一时间只执行一项环境安装，重复提交返回正在执行的任务。安装结束后宿主独立复查 `ready`。支持环境脚本但只提供 `ready`、`needs_install` 的旧工具包可继续走原有依赖流程，`command` 可以省略。缺少环境脚本时，环境入口提示更新工具包。

## 面板操作

| 动作 | 请求 | `data` |
| --- | --- | --- |
| `panel overview` | `{view_revision?}` | `{view_revision,card_count,document_count,code_count,types,recent_cards}` |
| `panel cards` | `{view_revision?,query?,type?,tag?,cursor?,limit?}` | `{view_revision,items:[{id,title,type,tags,summary}],next_cursor}` |
| `panel search` | `{view_revision?,query,tags?,top_k?}` | `{view_revision,matches,truncated}`，候选沿用整卡检索字段和权重 |
| `panel read` | `{view_revision?,card_id}` | 完整读卡结果与 `view_revision` |
| `panel graph` | `{view_revision?,card_id,kinds?,cursor?,limit?}` | `{view_revision,nodes:[{id,title,kind,ref_id?}],edges:[{source,target,kind}],next_cursor}` |
| `panel graph` | `{scope:"global",view_revision?}` | `{view_revision,nodes,edges,node_count,edge_count,truncated}` |
| `panel graph` | `{scope:"neighbors",node_id,view_revision?,kinds?,cursor?,limit?}` | `{view_revision,nodes,edges,next_cursor}` |
| `panel raw-list` | `{path?,cursor?,limit?}` | `{path,items:[{name,path,kind,size,category?,empty?}],next_cursor}` |
| `panel raw-path` | `{path}` | `{name,path,kind,size,absolute_path}`，供可信文件服务使用 |
| `panel raw-save` | `{path,staged_path,expected_size?,expected_sha256?}` | `{name,path,kind,size,sha256}` |
| `panel raw-mkdir` | `{path}` | `{path}`，阶段 `created` |
| `panel raw-rmdir` | `{path}` | `{path}`，阶段 `removed` |
| `panel intake-categories` | `{}` | `{categories:[{id,label,description}]}` |
| `panel intake-preflight` | `{files:[{path,staged_path,size,sha256}]}` | `{categories,items,ignored}` |
| `panel intake-save` | `{category,document_path,files:[{path,staged_path,expected_size,expected_sha256}]}` | `{name,path,kind,size,sha256}` |

OpenFlow 的绑定响应使用 `ETag` 标识所选知识库。浏览器后续以 `If-Match` 传回该值，宿主对旧绑定的请求返回 `KNOWLEDGE_BINDING_CHANGED`。它与 CLI 的 `view_revision` 分别标识库绑定和发布版本。首次校验通过 `doctor` 检查配置和规则，再试读原件根目录。依赖缺失阻止校验时，宿主返回 `KNOWLEDGE_BINDING_DEPENDENCIES_REQUIRED`，界面引导先安装环境再校验。确认保存绑定时才尝试读取 `overview`，发布视图缺失时执行一次 `maintain reindex`。

`/api/knowledge/operation` 只接受已列入宿主允许列表的操作及参数。发布卡片的路径深链由宿主先查出卡 ID，再调用 `panel read`，并核对返回的卡 ID 和路径。CLI 的 `panel read` 接收 `card_id` 和可选的 `view_revision`。

`overview` 的文档和代码数量分别去重统计被正式卡引用的来源。类型项为 `{type,count}`，最近卡片为 `{id,title,type}`，按文件更新时间取至多 10 张。类型由目录映射，旧 draft 不进入面板，其他旧卡仍可浏览。卡片列表按 ID 排序，查询可按正文词项、卡片类型和单个标签过滤。标题、摘要和标签只显示列表所需的短值，完整内容可用 `read` 取得。

## 图谱

带 `scope` 的请求共享由发布事务生成的图。节点包括正式卡、被这些卡引用的原件及代码文件，保留没有关系的正式卡。节点字段为 `{id,kind,ref_id,title,path}`。图 ID 按类型固定为 `card/<ref_id>`、`document/<ref_id>` 或 `code/<ref_id>`；读卡或查来源时传原始 `ref_id`。路径与对应卡片或来源登记一致。边为 `{source,target,kind}`，两端使用图 ID。边类型是 `doc_ref`、`code_ref`、`card_link`、`related_to`。同卡同来源的多个定位聚为一条边。指向同一发布视图内另一张卡的有效 Markdown 链接按方向去重，旧卡显式声明的 `related_to` 保留方向和独立类型。具体引用定位通过读卡获得。

- `global` 提供全库轻量拓扑。响应包含全库节点与关系总数，画布可按类型筛选。最多返回 4,000 个节点、15,000 条边，并限制单次 JSON 为 4 MiB。超过任一上限时稳定地返回部分数据并标记 `truncated: true`，每条已返回的边两端都在节点列表中。
- `neighbors` 从任意图节点读取传入和传出关系，包括来源到引用卡的反向浏览。逐点调用可继续沿图展开。中心始终返回，`kinds` 只筛选另一端；每页默认 30 条边，最多 50 条边和 51 个节点。下一页使用原节点、筛选条件、同一 `view_revision` 和原样传回的 `next_cursor`。最后一页游标为 `null`。
- 不传 `scope` 时沿用按 `card_id` 读取一跳的旧接口和节点 ID。历史面板版本可继续用于旧接口。首次使用新图谱时，若发布视图缺少图索引，执行 `maintain reindex` 构建新版本。

其他列表每页最多 100 项，默认每页 30 项。实时原件目录使用名称排序，原件增删会在之后的请求中反映。

## 正式知识版本

执行 `maintain reindex --json` 构建首个面板版本，包括空知识库。成功的 P5 和显式重建在现有 SQLite 写事务内发布新 `view_revision`。重建失败保留上次成功版本。面板查询直接读取发布表，返回轻量分页数据。绑定或维护流程遇到 `PANEL_VIEW_UNAVAILABLE` 时可执行一次重建。SQLite 锁争用导致读取暂时失败时返回 `PANEL_VIEW_BUSY`，客户端稍后重试同一读请求。版本已换时，客户端收到 `PANEL_REVISION_MISMATCH` 后刷新；筛选不匹配的游标返回 `PANEL_CURSOR_INVALID`。P5 在发布成功后更新本机最新回执。回执写入失败时，P5 仍返回 `completed`，并在 `data.receipt_warning` 报告文件错误。自动化应使用本次命令返回的结果。

Agent 可用 `panel search` 获取候选与版本，将该版本传给 `panel read` 读取同一发布版本。`read --input - --json` 同样接受 `{card_id,view_revision}`。已有无版本的 `read`、`search` 与 `source list` 保持各自的查询语义。版本化详情通过 `card_links: [{target,card_id,anchor?}]` 给出可生成深链的相对链接。 `target` 含正文中的原始片段，`anchor` 是已核对的解码后锚点。导航、原件、外部链接、图片、代码示例和不存在的锚点不进入这个映射。`heading_anchors: [{anchor,line}]` 提供治理解析器支持的正文标题锚点，行号从 `body` 的第一行起算。客户端应按源行设置这些锚点。旧投影可在下一次发布或重建后补出这些字段。

P4 检查在本批暂存记录实际核对过的来源字节。P5 将这些引用和精确来源版本关联到现有来源登记，正式卡保持审阅时的字节。卡片关联摘要统一 CRLF/LF，原件 SHA-256 按原始字节计算。重建只使用已持久化的绑定。对同样的卡片和引用重新核对并发布时，关联更新为这次核对的版本，历史快照仍可按 ID 查询。

版本化引用的 `source_version` 为 `bound` 时提供 `snapshot_id` 和 `source_sha256`，客户端可用 `source resolve` 发送 `{source_id,snapshot_id,hash?}` 取得精确原件。OpenFlow 文件接口接受快照 ID、SHA-256 或完整 Git 提交对象 ID 作为版本参数。宿主核对返回的来源 ID，确认制品位于绑定库的 `artifacts/sources/` 下，发给浏览器之前复算字节的 SHA-256。固定字节可通过已登记 Git 对象、同 SHA-256 的原件或本机证据对象恢复。本机证据对象留在 Git 忽略的目录。干净检出保留绑定，缺少对应字节时返回来源不可用。

引用没有固定版本时，OpenFlow 标注「引用版本未记录」。来源登记有 `processed_hash` 时按该摘要读取。没有摘要且路径位于 `docs-raw/` 时，打开当前原件。预览沿用引用定位。文本显示可定位的原始行号与高亮范围，PDF 打开定位页。显式快照缺失或关联不明确时显示 `unavailable`，预览提示该版本不可用。

## 实时原件

`path` 相对 `docs-raw/`，空串表示目录根。目录项 `kind` 为 `directory` 时 `size` 为 `null`，普通文件为 `file`。目录浏览读取物理文件，可显示尚未登记的文件。链接、隐藏项和本机 dbox 映射配置不参与浏览。保存目标必须是已有普通目录下支持入库的文件名，原件投递限于仓内目录。

目录项的 `category` 表示可作为归档分类的普通目录，`empty` 表示该分类物理为空。即使目录里只有隐藏文件，也不能通过 `raw-rmdir` 删除，命令返回 `RAW_DIRECTORY_NOT_EMPTY`。用 `raw-mkdir` 在根或已有分类下创建一个子目录，遇到同名或大小写冲突时返回 `RAW_TARGET_EXISTS`。特殊目录 `sources/`、资料包及其子目录不参与分类或目录变更。删除空目录不改动已有来源记录。

OpenFlow 先在服务端完整接收上传，再将可信的绝对暂存文件名传给 `raw-save`。浏览器只提供业务相对路径和字节，由宿主构造 `staged_path`。CLI 流式校验并写到目标目录的临时文件，同目录原子提交完整字节。目标已存在或与同目录的名称只差大小写时，返回 `RAW_TARGET_EXISTS`。文件大小或 hash 对不上返回 `RAW_STAGE_MISMATCH`。暂存文件由宿主清理，返回文件相对路径与 SHA-256 即可确认保存。原件注册及正式知识更新由之后的 CI 完成。

OpenFlow 批量上传使用 `intake-preflight`。CLI 从暂存文件读取有限的样本，返回当前原件目录的分类、标题和短摘录，以及每个 Markdown 本地图片的匹配结果。分类来源是绑定库中实际存在的普通目录，支持诸如 `protocols/2026` 的多级路径。分类 ID 和显示名均使用该相对路径。`intake-categories` 可单独读取最新分类。图片按文档相对路径匹配上传文件。外部图片链接显示提示，内嵌位图随 Markdown 原文保存。

用户为整批指定分类时，预检通过后宿主直接归档。分类失效或本地配图缺失时留在待处理状态。默认 AI 建议由宿主调用模型，用户可逐份修改并确认后归档。每份文档及其配图通过一次 `intake-save` 保存，CLI 复核分类目录、字节和附件关系，并按原相对路径提交资料包。并发提交时，CLI 在库的原件写入锁内复核分类目录和目标。相同目标和字节的重试返回原有回执，同名异内容返回冲突。宿主逐份保留成功回执，批内个别归档失败可重试未完成项。P1 只登记资料包的主文档，从清单校验并解析配图。需要修订图片时按新资料版本归档。

`raw-path` 返回已校验普通文件的真实路径，供可信服务按文件权限提供下载或预览。浏览器只接收相对引用和内容。找不到路径返回 `RAW_NOT_FOUND`。原件目录读取与投递不触发入库扫描、卡片更新或索引重建。
