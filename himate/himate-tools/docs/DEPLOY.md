# 安装与部署

用户首次安装按以下顺序进行。通过 npm 安装模型和 CLI，检查命令版本，运行 `knowledge setup`，再用 deploy 脚本安装 Skills 和 Workflows，最后启动 OpenFlow。领域知识仓的 `docs-llm-wiki/HiMate知识库使用指南.md` 提供页面操作说明。

## 安装模型与 CLI

执行机器需要 Node.js 18 或更新版本，以及带 pip 的 Python 3.10–3.12。使用运行 OpenFlow 的同一账户，先配置团队提供的内网 npm 源，再执行以下命令。

```sh
npm install -g @himate/knowledge-models
npm install -g @himate/knowledge-cli
knowledge --version
knowledge setup
```

npm 注册全局 `knowledge` 命令。模型包校验并准备本机 OCR 模型，CLI 包安装运行代码。`knowledge setup` 使用选定的 Python 执行 `python -m pip install -r`，安装锁定依赖并复查。该解释器应有可用的 pip，安装位置应允许写入。

使用会拦截安装脚本的 npm 客户端时，按其要求授权两个包的安装脚本。内网源和 npm 脚本策略的完整示例见 [npm 发布与安装](NPM-PUBLISH.md)。

## 安装 Skills 与 Workflows

能力安装器由 `himate-skills` 维护。进入该目录，Windows 运行 `.\deploy.ps1`，Linux 运行 `sh ./deploy.sh`，按提示选择宿主的能力目录。脚本从自身的 `skills/` 和 `workflows/` 安装包，安装完成后输出各目标的数量。

自定义目标目录、无人值守安装和安装测试见[能力仓安装说明](../../himate-skills/README.md)。

## 启动 OpenFlow

确认终端运行 `knowledge --version` 有版本输出，随后启动或重启 OpenFlow。OpenFlow 从启动账户的 PATH 查找全局命令，在页面上绑定含 `config.yml` 和 `docs-raw/` 的知识根。非默认安装目录需与宿主实际加载的能力目录一致。

OpenFlow 页面的环境检查调用 `knowledge doctor --environment-only --json`，安装环境调用 `knowledge setup --jsonl`，根据 CLI 输出显示阶段进度和最终结果。环境操作可以在绑定前执行。

Agent 通过 SSH 在另一台机器执行时，在那台机器安装 npm 包和依赖，并使用其本机路径。知识根的 `config.yml` 和 `AGENTS.md` 由项目负责人维护。

## 检查与排查

```sh
knowledge doctor --environment-only
knowledge doctor --knowledge-root "<知识根绝对路径>" --json
```

环境结果中，`ready` 表示依赖和命令就绪，`needs_install` 表示依赖缺失或版本不匹配，`needs_cli` 表示命令待注册或修复。安装日志保存在 `~/.himate/knowledge/logs/`。

需要选择 Python 时，将 `HIMATE_KNOWLEDGE_PYTHON` 设为解释器绝对路径。终端和 OpenFlow 使用同一个设置。宿主也可通过 `OPENFLOW_KNOWLEDGE_PYTHON` 单独选择解释器，变更后重启。

Linux 的 npm 全局目录需要允许当前账户写入，并将其 `bin/` 加入 PATH。Windows 安装后使用新终端检查命令。PowerShell 提示 npm 脚本执行策略受限时，可用 `npm.cmd` 执行相同安装命令。

## 模型位置

`@himate/knowledge-models` 把完整模型集安装到当前账户的 `~/.himate/knowledge/tools/deploy/models/docling-cpu/`，安装时校验文件、合并分片。CLI 升级会保留模型。使用 `standard` OCR 且未指定模型位置时，解析器使用这套本机模型。

已有知识库显式配置 `artifacts/models/` 下的模型目录时，解析器使用该配置。日常用户按上述 npm 安装流程准备模型即可。模型来源与文件清单见[模型说明](../distribution/models/README.md)。
