# HiMate 知识库工具包

`himate-tools/` 提供 Windows 和 Linux 安装入口、知识 CLI、共用治理规则、依赖清单和离线 OCR 模型。一套工具可服务多个知识仓。`himate-skills/` 单独交付 Skill（含指引、参考和模板）以及 Workflow（节点、角色、出口和画布）。

在本目录运行 `.\deploy.ps1` 或 `sh ./deploy.sh` 安装依赖和能力。部署默认使用同级的 `himate-skills/`。能力放在别处时用 `-CapabilitiesRoot` 或 `--capabilities-root` 指定。需要为某个库准备 OCR 时，显式传 `-KnowledgeRoot` 或 `--knowledge-root`。

安装后使用所选解释器启动本目录的 `knowledge.py`，并传入数据所在主机上的知识根。例如：

```powershell
python -B "D:\Department Tools\himate-tools\knowledge.py" doctor --knowledge-root "E:\业务\himate-knowledge-xxx" --json
```

安装参数和模型准备见[部署说明](tools/deploy/README.md)，接口、开发和验证见[开发文档](docs-llm-wiki/README.md)。日常操作见领域知识仓的 `docs-llm-wiki/使用说明.md`。知识仓提供自己的 `AGENTS.md`、`config.yml`、`docs-raw/`、`knowledge/` 和 `governance/sources.lock.yaml`。
