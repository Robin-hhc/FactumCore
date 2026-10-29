# 首次准备与执行

## 项目与能力各放一处

`repo/` 表示实际业务工作区，`K` 是根 `config.yml` 中的 WiFi 知识根；`S`、`F` 是实际执行端已安装的 Skill／Workflow 目录。

| 内容 | 位置 |
|---|---|
| 知识根、代码模块和其他项目配置 | 用户维护的 `repo/config.yml` |
| 原件、卡片和领域治理 | 既有 K 布局 |
| setup 脚本及依赖清单 | 实际执行端已安装 `S/hs-knowledge-explore/` 内 |
| 远端连接与命令执行 | OpenFlow／宿主已有的 SSH MCP |
| 稿件、请求、记录、索引和报告 | 实际执行端 K 已有 `.build/`、`logs/`、`artifacts/` |

默认使用执行端已有全局 Python，不为正常使用新增虚拟环境、机器绑定、登记目录或工具副本。Skill／Workflow 的安装由宿主既有方式完成，setup 不复制能力或修改宿主。

## 按需首次运行 setup

只在首次运行依赖尚未准备，或需要复查依赖时运行 setup。已有有效上下文和可用依赖时，按 [知识库任务入口](../SKILL.md) 直接转交对应已安装能力，不为每次 ingest、query、lint 或 status 重跑 setup。

先由 Agent 读取实际业务仓 `AGENTS.md`、项目配置、解析后的 `K/AGENTS.md` 与文档入口，并确认实际全局解释器；从项目根执行本包 `scripts/setup.py`，默认读取当前 `config.yml`。目标代码仓在远端时，先使用宿主已有 SSH MCP 进入远端项目根，再用该端已安装的脚本与 Python 执行相同命令。业务仓使用实际 `AGENTS.md`；分发的 `AGENTS.md.example` 由人按真实仓复制或合并，setup 不复制模板，`ready` 也不证明业务入口已准备：

```text
python PATH_TO_THIS_SKILL/scripts/setup.py --workspace-config config.yml
```

`PATH_TO_THIS_SKILL` 必须是实际执行端已安装能力的位置；调用端路径不能直接当作远端路径。setup 直接在当前执行端检查依赖和读取项目配置，不配置、选择或建立 SSH 连接。

脚本按配套运行锁检查当前解释器。依赖已齐不安装、不创建文件；缺失或版本不符时，pip 安装到同一全局解释器，再重新核对。包源沿用机器既有 pip 配置；明确的内网源使用 `--index-url`，匹配系统／CPU／Python 的离线 wheel 使用 `--wheelhouse`。只检查而不安装可用 `--check-only`。

| 返回状态 | 含义与后续 |
|---|---|
| `ready` | 当前全局 Python 依赖匹配、项目配置已读取；harness 再核查路径和实际节点 |
| `missing_dependencies` | 只检查模式发现缺项，按列出的库准备后重试 |
| `failed` | 读取、安装或配置失败，保留诊断并处理实际问题 |

setup 不生成 catalog、registry 或 binding。业务 CLI 不要求这些登记文件，默认加载当前规则锁并核验文件；人工可逐个调用，OpenFlow 校验 Workflow 交棒。setup 成功也不证明已入库、已有活动索引或宿主 Workflow 已触发。

## 远端项目使用宿主 SSH MCP

目标代码仓在远端时，先由用户或部署维护者在 OpenFlow 配置、启用并验证 SSH MCP，并让需要远端执行的角色可调用它。Agent 再通过该 MCP 执行 setup、业务节点、源码读取和仓库操作，使用远端实际项目根、全局 Python 与已安装 Skill 路径；连接信息由宿主管理，Skill 不维护另一套 SSH 配置。

harness 须核对执行端能力入口与实际结果。执行端能力缺失时报告具体缺口，按宿主既有部署方式处理；不将调用端脚本路径当成远端入口。SSH 认证、可达性、权限和命令结果依据真实调用判断，不要求建立专用连接器或复制一份部署工具。

## 后续使用和产物

项目结构继续只改根 `config.yml`。机器全局依赖已安装后，重复 setup 脚本只是检查并读取入口。首次项目准备时，Agent 继续按 [首次初始化 CodeGraph](../SKILL.md#首次初始化-codegraph) 遍历配置中的代码仓；这部分由 Agent 执行，setup 脚本不建图。所需 MCP 由宿主配置并提供，按任务核对是否可调用。日常 ingest、query、lint 或 status 按 [任务路由](../SKILL.md) 继续对应能力，已有准备结果直接复用。

Agent/harness 使用已安装的 Skill／Workflow 执行任务；跨机器节点及其子调用、来源读取和生成物留在项目所在服务器。稿件、操作请求与结果使用 K 的 `.build/`，正式记录与来源留痕使用 `logs/`，索引和报告使用 `artifacts/`，不新增外部产物位置。

SSH 结果不明或连接中断时，先由 harness 核对原执行端进程、操作记录、journal 和活动代，再决定续办；不推断远端未执行，也不重复已提交的写入。

先验证一次实际 status；新项目操作列表为空正常。再选一份原件走 ingest、独立内容复核、lint、本地入库、索引及目标查询，并在活动代激活后用原回执 read 检查同代内容和来源定位。独立复核、单写、恢复和证据要求沿用业务规则，入口准备不代替这些检查。
