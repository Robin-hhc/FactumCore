# CodeGraph 接口与 MCP 接入

## 官方依据与版本核对

本 Skill 使用 [colbymchenry/codegraph](https://github.com/colbymchenry/codegraph)。以下是一手参考；实际命令及参数以部署机器的版本、子命令帮助和 MCP Schema 为准，不把网页最新接口直接套到旧版。

| 依据 | 用于核对 |
|---|---|
| [安装与项目初始化](https://colbymchenry.github.io/codegraph/getting-started/installation/) | Agent 注册与每项目 `init` 分开；`install --print-config <id>` 可生成受支持宿主的片段 |
| [CLI](https://colbymchenry.github.io/codegraph/reference/cli/) | `init`、`status`、`explore`、`sync` 的用途；完整重建另属 `index` |
| [MCP Server](https://colbymchenry.github.io/codegraph/reference/mcp-server/) | 宿主启动 `serve --mcp`，默认暴露 `codegraph_explore`；其他工具不保证默认可见 |
| [Integrations](https://colbymchenry.github.io/codegraph/reference/integrations/) | 受支持宿主及手工 stdio 配置；自动安装器可能改宿主配置与指令文件 |
| [Troubleshooting](https://colbymchenry.github.io/codegraph/troubleshooting/) | 文件排除、MCP 连接、手工同步和不同系统索引目录问题 |

不要把其他名为 CodeGraph 的实现、`codegraph-rust` 的 `--target` 等选项，或某机器的工具前缀复制为本项目必需接口。CLI 支持情况必须从实际 `--help` 获取；某个参数没有出现就不使用。

下文 command／args、CLI 工作目录及 projectPath 示例以索引、源码与官方 MCP 位于同一执行主机为前提。服务器项目的命令通过已授权 SSH 在服务器原生路径执行，宿主使用实际已支持并配置好的远端官方 MCP 连接；没有接入时报告缺口，不宣称 MCP 可用，不把 Windows 映射盘／UNC 的 projectPath 交给本机 MCP，也不通过 Samba 读取或建立副本图谱。本说明不增加 CodeGraph 的远程 API 参数或自建查询路由。

## 最小逐模块操作

由执行工具将工作目录明确设置为当前模块绝对路径后，分别调用：

```text
codegraph --version
codegraph init --help
codegraph status --help
codegraph serve --help
codegraph status
```

仅当前根没有自身索引且版本行为已核实时运行：

```text
codegraph init
codegraph status
```

若可执行文件不在 PATH，改用实际路径；这是进程参数，不把整行文本当作路径传入。每模块单独设置工作目录，不假设上一条命令的 `cd` 在下一次工具调用仍然生效。

已有索引只复用；失败项不删除、不加 `--force`、不自动 `unlock`。重新 setup 只补缺失项。`init` 的默认附属文件行为可能随版本变化，执行前检查帮助／官方源码并在结果中列出。CodeGraph 安装和宿主注册不等于已完成项目建图。

已核验的 v1.6.0 会在新索引目录内创建 `.gitignore`；watcher 不可用且目标为 Git 仓时，`init --yes` 还可能自动选择安装 sync hook。此 Skill 不使用 `--yes`，交互时选 manual；无法控制交互则报告待处理。空图触发的“索引被忽略仓”询问也不默认接受，否则会写入项目 `codegraph.json` 的 `includeIgnored` 并再次索引。具体行为见官方 [v1.6.0 CLI](https://github.com/colbymchenry/codegraph/blob/v1.6.0/src/bin/codegraph.ts) 和 [installer](https://github.com/colbymchenry/codegraph/blob/v1.6.0/src/installer/index.ts) 的 `offerIndexIgnoredRepos`、`offerWatchFallback`。

检查实际 CodeGraph 配置、忽略规则和受支持语言。尤其项目本身可能将业务代码目录 Git 忽略：必须用模块内实际文件验证收录，不能用知识库目录的索引代替。不要为了得到非零符号数自动清除项目的忽略规则。

## MCP 片段

下面展示通用 JSON stdio 形状，供使用 `mcpServers` 的宿主适配；它不是所有宿主通用的配置文件。先确定宿主支持的格式和 CLI 参数，再生成最终片段。`<...>` 全部替换成运行时解析值，不原样落入配置：

```json
{
  "mcpServers": {
    "codegraph": {
      "type": "stdio",
      "command": "<CodeGraph 可执行文件绝对路径>",
      "args": ["serve", "--mcp", "--path", "<一个已初始化模块的绝对路径>"]
    }
  }
}
```

仅当实际 `serve --help` 支持 `--path` 时使用上面的路径参数；否则按宿主支持的工作目录配置启动，或交付对应版本的官方接入方案。默认根选择已准备模块，不指向没有图谱的 `repo/`。已存在同名服务时先核对，避免覆盖另一项目的配置。

支持的宿主可参考 `codegraph install --print-config <实际宿主ID>` 的输出。该选项是否存在、ID 是否受支持，以本机 `install --help` 为准；不使用无参数 `codegraph` 或 `codegraph install --yes` 来试探，因为它们可能写入配置。无需给所有工具配置自动允许权限。

MCP 由宿主启动。片段已生成、文件已写入、宿主已加载和逐模块查询已验证是不同状态；根据实际进度报告。宿主不支持当前多项目 Schema 时保留明确缺口，不把配置片段当作运行成功证据。

## 后续查询

从知识卡继续分析时，可复用 `hs-knowledge-query` 返回的 `sources`：代码来源的 `resource.repo_id`、`resource.path`、`source_ref.locator` 和已恢复的 `text` 提供源码线索。直接读卡时，由 `Claim.source_refs` 对应本卡 `sources`，再由来源锁找到文件与固定快照；卡头的结构化引用可承担这一职责，不要求正文另有可点击链接。一次读取多条结论时来源可能合并，需精确区分可用原搜索 `receipt_ref`、`card_id` 和单个 `claim_ids` 做同代精读。

先按受信项目配置及来源 scope 解析真实源码文件，再选择包含该文件的已登记模块索引根作为 `projectPath`；不要将来源 ID、文件父目录或不同基准的相对路径直接当模块根。读取来源行段得到实际函数名或文件位置后，交给官方 MCP 追查调用、条件和相关定义。卡片固定快照可能是历史版本，CodeGraph 不会据此自动切换源码版本；核对所问版本及文件指纹，版本不同时只将图谱结果作为定位线索，不替代原快照证据，也不自动执行 Git 切换。

从实际模块映射取得绝对目录，替换示例中的占位值：

```json
{
  "projectPath": "<当前要查询的模块绝对路径>",
  "query": "<实际符号名、文件名或调用流程问题>",
  "maxFiles": 4
}
```

这是 `codegraph_explore` 的参数示意；先核对当前 MCP 工具 Schema，再调用实际暴露的工具名。工具通常按 `projectPath` 向上寻找最近索引，因此 setup 要核对每个模块自己的索引，Q6 要核对返回文件确属所选模块。多根调用分别使用各自路径；一次调用不证明不同索引之间建立了调用边。

可选 CLI 诊断是在目标模块工作目录下运行 `codegraph explore "<实际符号名>"`，先核对帮助；它只证明 CLI 读取能力，不能代替宿主 MCP 验证。存在索引但内容过期时，按该版本 `sync` 的帮助手工同步。

v1.6.0 的多项目查询读取其他根的已有数据库，watcher 仅附着会话默认根，见官方 [MCP tools 实现](https://github.com/colbymchenry/codegraph/blob/v1.6.0/src/mcp/tools.ts)。因此“单服务可查询多根”不等于“所有根自动刷新”。交付时按实际版本明确每根服务的监听范围，或给出在该模块目录执行 `codegraph sync` 的使用方式；不要自行创建后台服务来补齐监听。

索引没有覆盖、标记文件已变化、当前源码未返回或条件存在歧义时，读取对应实际文件补齐证据。静态图谱提供源码定位和结构线索，未知宏、构建及跨端条件继续保持 unknown。
