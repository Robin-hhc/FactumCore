# HiMate 知识库工具包

`himate-tools/` 提供 Windows 和 Linux 安装入口、知识 CLI、共用治理规则、依赖清单和离线 OCR 模型。一套工具可服务多个知识仓。`himate-skills/` 单独交付 Skill（含指引、参考和模板）以及 Workflow（节点、角色、出口和画布）。

配置好内网 npm 源后，按以下顺序安装。执行机器需要 Node.js 18 或更新版本，以及带 pip 的 Python 3.10–3.12。 [npm 安装说明](docs/NPM-PUBLISH.md)

```sh
npm install -g @himate/knowledge-cli --registry http://10.143.57.12:4873 --allow-scripts=@himate/knowledge-cli
knowledge --version
knowledge setup
```

CLI 包注册全局 `knowledge`。`setup` 使用选定的 Python 安装基础锁定依赖并复查，安装位置应允许写入。可用 `HIMATE_KNOWLEDGE_PYTHON` 指定解释器绝对路径。文档解析工具和 OCR 模型按需准备。部署时更新配套的 Skills 和 Workflows，再启动或重启 OpenFlow。 [按需部署](docs/DEPLOY.md#按需准备文档解析)

终端和自动化统一使用 `knowledge`。下例检查指定知识库的配置和运行环境。

```powershell
knowledge doctor --knowledge-root "E:\业务\himate-knowledge-xxx" --json
```

OpenFlow 默认从宿主进程的 PATH 调用 `knowledge`。在运行 OpenFlow 的账户下全局安装 npm 工具包，确认宿主继承了 npm 命令目录后，即可绑定知识库。「环境检查」和「安装环境」调用同一个 CLI 的 `doctor --environment-only` 和 `setup`。Skills 和 Workflows 由 `himate-skills` 仓内的 `.\deploy.ps1` 或 `sh ./deploy.sh` 安装。 [能力安装说明](../himate-skills/README.md)

工具包内 `runtime/` 放 CLI、运行依赖和规则，`distribution/` 放 npm、宿主环境入口和独立 OCR 模型包，`evals/` 放测试，`docs/` 放安装与开发说明。知识仓提供自己的 `AGENTS.md`、`config.yml`、`docs-raw/`、`knowledge/` 和 `governance/sources.lock.yaml`。 [开发文档](docs/README.md)
