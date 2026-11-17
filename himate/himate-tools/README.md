# HiMate 知识库工具包

`himate-tools/` 提供 Windows 和 Linux 安装入口、知识 CLI、共用治理规则、依赖清单和离线 OCR 模型。一套工具可服务多个知识仓。`himate-skills/` 单独交付 Skill（含指引、参考和模板）以及 Workflow（节点、角色、出口和画布）。

配置好内网 npm 源后，运行 `npm install -g @himate/knowledge-cli`。使用 npm 12 时加上 `--allow-scripts=@himate/knowledge-cli`。安装完成后，运行 `knowledge setup`，它会用选定的 Python 执行 `python -m pip install -r` 安装工具包锁定的依赖。该解释器需有可用的 pip，安装位置需允许写入。可用 `HIMATE_KNOWLEDGE_PYTHON` 指定解释器的绝对路径。完成后可以从任意工作目录通过 `--knowledge-root` 操作指定知识库。 [npm 安装说明](docs/NPM-PUBLISH.md)

终端和自动化统一使用 `knowledge`。下例检查指定知识库的配置和运行环境。

```powershell
knowledge doctor --knowledge-root "E:\业务\himate-knowledge-xxx" --json
```

OpenFlow 默认从宿主进程的 PATH 调用 `knowledge`。在运行 OpenFlow 的账户下全局安装 npm 工具包，确认宿主继承了 npm 命令目录后，即可绑定知识库。「环境检查」和「安装环境」调用同一个 CLI 的 `doctor --environment-only` 和 `setup`。需要从源码安装 Skills、Workflows 或准备离线 OCR 时，使用 `.\deploy.ps1` 或 `sh ./deploy.sh`。部署默认读取同级的 `himate-skills/`。 [部署说明](docs/DEPLOY.md)

工具包内 `runtime/` 放 CLI、运行依赖和规则，`distribution/` 放 npm、源码部署和独立 OCR 模型包，`evals/` 放测试，`docs/` 放安装与开发说明。知识仓提供自己的 `AGENTS.md`、`config.yml`、`docs-raw/`、`knowledge/` 和 `governance/sources.lock.yaml`。 [开发文档](docs/README.md)
