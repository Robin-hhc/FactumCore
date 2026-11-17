# HiMate 知识库工具包

`himate-tools/` 提供 Windows 和 Linux 安装入口、知识 CLI、共用治理规则、依赖清单和离线 OCR 模型。一套工具可服务多个知识仓。`himate-skills/` 单独交付 Skill（含指引、参考和模板）以及 Workflow（节点、角色、出口和画布）。

配置好内网 npm 源后，运行 `npm install -g @himate/knowledge-cli`，再运行 `knowledge setup` 准备当前 Python 的依赖。完成后可以从任意工作目录通过 `--knowledge-root` 操作指定知识库。 [npm 安装说明](NPM-PUBLISH.md)

OpenFlow 的「环境检查」和「安装环境」调用同一个 CLI 的 `doctor --environment-only` 和 `setup`。从源码部署时可用已选解释器直接运行工具包的 `knowledge.py`。下例检查指定知识库的配置和运行环境。

```powershell
python -B "D:\Department Tools\himate-tools\knowledge.py" doctor --knowledge-root "E:\业务\himate-knowledge-xxx" --json
```

需要安装 Skills、Workflows 或为指定库准备 OCR 时，使用 `.\deploy.ps1` 或 `sh ./deploy.sh`。部署默认读取同级的 `himate-skills/`。 [部署说明](tools/deploy/README.md)

命令与数据接口见[开发文档](docs-llm-wiki/README.md)。知识仓提供自己的 `AGENTS.md`、`config.yml`、`docs-raw/`、`knowledge/` 和 `governance/sources.lock.yaml`。
