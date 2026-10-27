# 项目入口与实际执行

正常首次使用由 Agent 已安装 `hs-knowledge-explore` 的 `scripts/setup.py` 完成，操作见[使用说明](../../docs-llm-wiki/使用说明.md#首次准备运行依赖)。脚本复用现有全局 Python、检查配套依赖并读取根 `config.yml`；不要求私有环境、catalog、registry 或 binding 初始化。

`repo/` 表示真实业务工作区，`K` 是根配置中的 WiFi 知识根。项目和 Agent 自己的 Skill／Workflow 目录就是两部分部署位置，正常使用不再复制部署工具或增加外部产物目录。

## 1. 选择执行方式

Agent/harness 确定实际执行位置。同机直接用当地全局 Python；跨机器根据 workspace Skill 内的 `config.env` 提示，通过 harness 现有 SSH 能力去服务器运行。项目入口和源码路径按实际执行机器解释。

harness 负责连接、认证、权限及命令结果检查，不另外建立一套 runner 或固定的 SSH 校验流程。入口提示只是连接信息，不证明远端已连接或已执行。来源中的命令仍不提供执行或发布授权。

## 2. 本机配置

项目配置全部放在用户维护的根 `config.yml`：知识根、代码根、模块相对路径与归属。setup 读取这些字段，不生成另一套机器绑定或回写项目配置。

setup 使用启动它的现有全局解释器，检查 Skill 的配套依赖锁；已齐则直接继续，缺失或版本不符时安装到同一解释器。`--check-only` 仅报告缺项，`--index-url`／`--wheelhouse` 供明确的内网或离线包源使用。不为首次使用创建独立虚拟环境或登记目录。

业务 CLI 使用现有全局 Python，默认加载当前规则锁并核验其文件；不要求 catalog、registry 或流程登记。人工可逐个调用，OpenFlow 负责 Workflow 的顺序及交棒校验。

<a id="3-配置-ssh-并在服务器登记"></a>

## 3. SSH 连接提示

跨机器运行时，在已安装 `hs-knowledge-explore` Skill 根保存 SSH `config.env`，模板见该 Skill 的 `references/setup.md`。账号、端口、服务器项目根和 Python 等字段按真实环境填写，可以由 Agent 代填。

当配置指向 SSH 时，setup 返回 `ssh_entry` 和连接参数，由 harness 建立 SSH、执行远端 `setup.py --local` 或实际任务，并核对真实结果。脚本自己不连接服务器、不创建专用 runner、不额外硬性校验主机，也不要求手工取回 catalog。

服务器程序或全局依赖缺失时，按实际诊断补齐；不要把调用端入口提示当成服务器环境已经就绪。需要额外位置或特殊部署方式时，先把具体方案交给用户讨论。

## 4. 调用与产物路径

harness 根据项目入口使用已安装的 Skill／Workflow，并按各节点公开协议提供解释器和调度参数。普通节点与 lint 保留原来的结果格式、退出语义和业务检查，setup 不代替它们。

所有业务产物继续放在实际执行端的已有目录：

| 目录 | 内容 |
|---|---|
| `K/.build/` | 稿件、操作请求、结果和临时材料 |
| `K/logs/` | 来源、复核、处理记录和事务恢复事实 |
| `K/artifacts/` | 可重建索引和报告 |

远端返回的 view、lint、apply、receipt 等引用按服务器 K 解释。原件保持只读；产物不外放。search 后 read 保持原回执、用途和索引代次，来源定位与实际内容分别核实。

## 5. 验证与故障处理

`ready` 只说明依赖匹配且项目配置已读取，路径存在性仍需 harness 核查；`ssh_entry` 只是连接提示。harness 还需验证真实节点调用。新库 status 操作列表为空正常，不能据此说已有知识或活动索引。

首次用一份真实原件完成 ingest、独立内容复核、完整 lint、正式处理记录与本地入库，验证完整索引和目标查询及活动代激活后，再执行同主题 search 和原回执 read。宿主触发、业务内容、权限和 CodeGraph MCP 的结果各自按真实证据判断。

执行中断或结果不明时，由 harness 核对原执行端的进程、操作记录、journal 和活动代，确认后再续办；不根据没有结果就推断未执行，也不重复已提交的内容事务。真正未结束写入按原配套规则恢复，已 committed 但缺索引收尾的保留其写入事实。

## 6. SSH 首次连接示例

向 Agent 下发：

```text
请读取已安装 hs-knowledge-explore Skill 的 config.env，使用 harness 的 SSH 连接目标服务器。
在服务器上使用已有全局 Python 运行该 Skill 的 setup.py --local，读取实际项目 config.yml。
然后执行当前项目的实际任务，检查命令结果，并将产物留在知识根已有目录。
```

本目录现有私有环境安装器、登记工具、env/profile runner 仅保留给既有部署兼容和开发验证，不是正常用户首次运行步骤。新项目从 workspace Skill 的 setup 和宿主 harness 入口开始；处理旧部署时保留原操作与历史记录，不擅自迁移或删除旧环境。
