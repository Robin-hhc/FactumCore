# HiMate 知识库工具包

同一个目录提供 Windows 和 Linux 安装入口、知识 CLI、共用治理规则、依赖清单、离线 OCR 模型、Skills 和 Workflows。执行端可把这个目录放在任意可访问的位置，并用同一份工具操作多个知识仓。

在本目录运行 `.\deploy.ps1` 或 `sh ./deploy.sh` 安装依赖和能力。需要为某个库准备 OCR 时，显式传 `-KnowledgeRoot` 或 `--knowledge-root`。

安装后使用所选解释器启动本目录的 `knowledge.py`，并传入数据所在主机上的知识根。例如：

```powershell
python -B "D:\Department Tools\himate-knowledge-tools\knowledge.py" doctor --knowledge-root "E:\业务\himate-knowledge-xxx" --json
```

安装参数和模型准备见[部署说明](tools/deploy/README.md)，接口、开发和验证见[开发文档](docs-llm-wiki/README.md)。日常操作见领域知识仓的 `docs-llm-wiki/使用说明.md`。知识仓提供自己的 `AGENTS.md`、`config.yml`、`docs-raw/`、`knowledge/` 和 `governance/sources.lock.yaml`。
