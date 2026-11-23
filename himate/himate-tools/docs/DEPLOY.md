# 安装与部署

在 OpenFlow 宿主部署 Skills 和 Workflows，在实际运行 `knowledge` 的机器上安装 CLI、模型和 Python 依赖。对于本地知识库，可在终端预装，也可从 OpenFlow 页面检查和补装。[HiMate 知识库使用指南](../../himate-knowledge-wifi-mp/docs-llm-wiki/HiMate知识库使用指南.md)

## 安装模型与 CLI

执行机器需要 Node.js 18 或更新版本，以及带 pip 的 Python 3.10–3.12。本地知识库使用 OpenFlow 启动账户。Windows 宿主通过 Samba 绑定共享目录时，使用现有 SSH MCP 所连接的 Linux 账户，在 Linux 对端执行以下命令。

```sh
npm install -g @himate/knowledge-models --registry http://10.143.57.12:4873 --allow-scripts=@himate/knowledge-models
npm install -g @himate/knowledge-cli --registry http://10.143.57.12:4873 --allow-scripts=@himate/knowledge-cli
knowledge --version
knowledge setup
```

npm 注册全局 `knowledge` 命令。模型包校验并准备本机 OCR 模型，CLI 包安装运行代码。`knowledge setup` 使用选定的 Python 执行 `python -m pip install -r`，安装锁定依赖并复查。该解释器应有可用的 pip，安装位置应允许写入。

命令包含团队内网源，并为两个包分别授权安装脚本。[npm 发布与安装](NPM-PUBLISH.md#3-安装)

## 安装 Skills 与 Workflows

能力安装器由 `himate-skills` 维护。进入该目录，Windows 运行 `.\deploy.ps1`，Linux 运行 `sh ./deploy.sh`，按提示选择宿主的能力目录。脚本从自身的 `skills/` 和 `workflows/` 安装包，安装完成后输出各目标的数量。

自定义目标目录、无人值守安装和安装测试见[能力仓安装说明](../../himate-skills/README.md)。

## 启动 OpenFlow

启动或重启 OpenFlow，使其加载部署好的能力。在知识库页选择含 `config.yml` 和 `docs-raw/` 的知识根，校验通过后保存绑定。非默认能力安装目录需与宿主实际加载的目录一致。

本地执行时，OpenFlow 从启动账户的 PATH 查找 `knowledge`。绑定前可以打开「环境检查」。缺少 CLI 时，点「同意并安装」后由宿主尝试执行上面的两条 npm 命令。缺少 Python 依赖时可点「安装环境」。检查调用 `knowledge doctor --environment-only --json`，补齐依赖调用 `knowledge setup --jsonl`。页面按 CLI 输出显示进度和结果。

Windows 上选择 Samba 映射盘或共享路径时，在现有 SSH MCP 设置中确认连接并添加 Windows 到 Linux 的路径映射。CLI、模型和依赖在 Linux 对端安装。确认 SSH 账户的 PATH 能找到 `knowledge` 后，回到 OpenFlow 重新校验。Linux 原生部署使用宿主本地路径，浏览器通过反代访问时执行端仍是 Linux 宿主。知识根的 `config.yml` 和 `AGENTS.md` 由项目负责人维护。

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
