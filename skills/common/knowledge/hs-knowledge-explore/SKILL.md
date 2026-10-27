---
name: hs-knowledge-explore
description: HiMate 知识库项目接口：首次准备运行依赖和项目入口，后续定位代码仓、知识根并加载上下文；跨机器按本 Skill 的 SSH 配置提示访问。
---

# hs-knowledge-explore

本 Skill 是知识库的项目接口。首次调用负责 setup 和入口读取；后续缺少入口信息时，通过只读发现找到代码仓、知识根并读取 `AGENTS.md`、`config.yml`。已有有效上下文就直接复用，无需重复 setup。

首次使用当前项目时，先运行本包 `scripts/setup.py`。它复用执行机器现有的全局 Python，依赖已齐就直接读取项目配置；缺包或版本不符时，在同一解释器中安装配套依赖。项目配置全部来自用户维护的根 `config.yml`。

跨机器首次使用时，先将本包随附的 [config.env.example](config.env.example) 复制为同目录的 `config.env`，按文件内中文注释填写；实际 `config.env` 是本机私有配置，不提交或随包分发，同机使用可不创建。先读取本 Skill 的 `config.env`（存在时）。指向服务器就让 harness 通过 SSH 到其中的项目位置，再读取远端 `AGENTS.md`、`config.yml` 和实际知识根入口；同机则直接读取。存在 `LOCAL_DEPLOYMENT.md` 时读取当地约定。用执行机器的全局 Python 从实际项目根运行：

```text
python PATH_TO_THIS_SKILL/scripts/setup.py --workspace-config config.yml
```

路径来自 Agent 已安装的本 Skill 位置，不要求项目根保留能力源码。脚本返回 `ready` 表示依赖匹配且项目配置已读取；路径存在性和实际能力仍由 harness 核查。`ssh_entry` 只提供连接提示，Agent/harness 需按本 Skill 的 `config.env` 通过 SSH 到服务器执行 `setup.py --local` 或实际节点，并检查结果。参数及状态见 [首次准备与执行](references/setup.md)。

不创建独立虚拟环境、catalog／registry／binding 或额外部署目录。日常节点直接由 harness 使用已安装能力；节点默认读取当前规则锁并核验其文件；不要求 catalog 或流程登记，人工可逐个调用。请求、稿件、记录和索引继续使用实际知识根已有 `.build/`、`logs/`、`artifacts/`。

已有项目上下文直接复用；缺少入口信息时保留原只读发现 CLI，构造请求前读 [公开 API](references/public-api.md)。`code_root` 相对项目根，模块 `path` 相对代码根；以实际配置和文件提供线索，不从芯片／端／特性标签推断宏、构建或运行事实。

setup 不处理业务入库、CodeGraph、Git 或宿主配置。环境缺项、SSH 连接和权限问题由 harness 依据实际结果判断；需要新位置、系统组件或其他特殊处理时，先向用户说明方案。不将脚本返回的入口提示当作已验证远端连接，不将退出成功当作内容复核、代码证明或真实合入。

产物展示规则见 [writing-guide](artifacts/writing-guide.md)，复核见 [review-guide](artifacts/review-guide.md)。
