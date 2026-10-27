# 首次准备与执行

## 项目与能力各放一处

`repo/` 表示实际业务工作区，`K` 是根 `config.yml` 中的 WiFi 知识根；`S`、`F` 是 Agent 已安装的 Skill／Workflow 目录。

| 内容 | 位置 |
|---|---|
| 知识根、代码模块和其他项目配置 | 用户维护的 `repo/config.yml` |
| 原件、卡片和领域治理 | 既有 K 布局 |
| setup 脚本及依赖清单 | 已安装 `S/hs-knowledge-explore/` 内 |
| 跨机器 SSH 连接提示 | 同一 Skill 根的 `config.env` |
| 稿件、请求、记录、索引和报告 | 实际执行端 K 已有 `.build/`、`logs/`、`artifacts/` |

默认使用机器已有全局 Python，不为正常使用新增虚拟环境、机器绑定、登记目录或工具副本。Skill／Workflow 的安装由宿主既有方式完成，setup 不复制能力或修改宿主。

## 一次运行 setup

先由 Agent 读取项目入口并确认实际全局解释器；从项目根执行本包 `scripts/setup.py`，默认读取当前 `config.yml`：

```text
python PATH_TO_THIS_SKILL/scripts/setup.py --workspace-config config.yml
```

脚本先查看本 Skill 的 `config.env`。有 SSH 主机且执行方式未设为 local 时，只返回 `ssh_entry` 和连接信息，由 Agent/harness 完成连接与执行检查；它自己不连接服务器、不写额外 runner 配置，也不固定额外主机校验流程。

实际在项目所在机器执行时，用 `--local` 忽略调用端 SSH 提示：

```text
python PATH_TO_THIS_SKILL/scripts/setup.py --local --workspace-config config.yml
```

在实际执行端，脚本按配套运行锁检查当前解释器。依赖已齐不安装、不创建文件；缺失或版本不符时，pip 安装到同一全局解释器，再重新核对。包源沿用机器既有 pip 配置；明确的内网源使用 `--index-url`，匹配系统／CPU／Python 的离线 wheel 使用 `--wheelhouse`。只检查而不安装可用 `--check-only`。

| 返回状态 | 含义与后续 |
|---|---|
| `ready` | 当前全局 Python 依赖匹配、项目配置已读取；harness 再核查路径和实际节点 |
| `ssh_entry` | 只有连接提示，harness 去服务器运行 `--local` 或实际工作并检查结果 |
| `missing_dependencies` | 只检查模式发现缺项，按列出的库准备后重试 |
| `failed` | 读取、安装或配置失败，保留诊断并处理实际问题 |

setup 不生成 catalog、registry 或 binding。业务 CLI 不要求这些登记文件，默认加载当前规则锁并核验文件；人工可逐个调用，OpenFlow 校验 Workflow 交棒。setup 成功也不证明已入库、已有活动索引或宿主 Workflow 已触发。

## SSH 配置放在本 Skill 内

本包根的 [config.env.example](../config.env.example) 随 Skill 分发，包含全部连接字段和中文注释。需要跨机器时，将它复制为同目录的 `config.env`，再按注释填写实际连接信息；同机使用可不创建。实际 `config.env` 是本机私有配置，不提交、不随能力包分发，也不放进业务资料。它是普通连接数据，不作为 shell 脚本执行。

`SSH_PORT`、账号和密钥路径按实际需要填写，可复用 harness 已有连接设置。`REMOTE_PROJECT_ROOT` 为服务器原生路径，`PYTHON` 为服务器现有全局解释器的命令或路径。`EXECUTION_MODE=local` 或未填 `SSH_HOST` 时，setup 直接在当前机器处理；`--local` 用于 harness 已到服务器后的实际执行。

这些字段只提示 Agent/harness 该去哪里运行。`ssh_entry` 不上传 Skill 脚本；harness 须确认服务器上实际能力入口可调用，调用端的 Skill 路径不能当作远端路径。执行端能力缺失时先报告并讨论方案。

SSH 认证、端口、可达性、权限和命令结果由 harness 依据真实执行判断；不要求建立专用连接器或复制一份部署工具。缺少信息先问用户，特殊处理先说明具体方案，不保存密码或私钥正文。

## 后续使用和产物

项目结构继续只改根 `config.yml`。机器全局依赖已安装后，重复 setup 只是检查并读取入口；它不建立常驻服务，不自动初始化 CodeGraph 或进入 ingest。

Agent/harness 使用已安装的 Skill／Workflow 执行任务；跨机器节点及其子调用、来源读取和生成物留在项目所在服务器。稿件、操作请求与结果使用 K 的 `.build/`，正式记录与来源留痕使用 `logs/`，索引和报告使用 `artifacts/`，不新增外部产物位置。

SSH 结果不明或连接中断时，先由 harness 核对原执行端进程、操作记录、journal 和活动代，再决定续办；不推断远端未执行，也不重复已提交的写入。

先验证一次实际 status；新项目操作列表为空正常。再选一份原件走 ingest、独立内容复核、lint、本地入库、索引及目标查询，并在活动代激活后用原回执 read 检查同代内容和来源定位。独立复核、单写、恢复和证据要求沿用业务规则，入口准备不代替这些检查。
