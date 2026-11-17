# npm 发布与安装

两个包，分别发布：

| 包 | 目录 | 体积 |
|---|---|---|
| `@himate/knowledge-cli` | 仓库根目录 | 约 1.5MB |
| `@himate/knowledge-models` | `tools/deploy/models/` | 约 397MB |

## 1. Verdaccio 准备

大包需要放开请求体上限，否则模型包会返回 413：

```yaml
# config.yaml
max_body_size: 1gb
```

首次发布前登录：

```bash
npm adduser --registry http://10.143.57.12:4873
```

## 2. 发布

```bash
# CLI
cd <himate-tools>
npm publish --registry http://10.143.57.12:4873

# 模型
cd <himate-tools>/tools/deploy/models
npm publish --registry http://10.143.57.12:4873
```

## 3. 安装

Windows 和 Linux 使用相同的命令。npm 11 默认执行安装脚本，可以直接安装。

```bash
npm i -g @himate/knowledge-cli --registry http://10.143.57.12:4873
knowledge setup
# 需要离线 OCR 模型包时
npm i -g @himate/knowledge-models --registry http://10.143.57.12:4873
```

npm 12 默认拦截未授权的安装脚本。全局安装时为各包授权执行其安装脚本。

```bash
npm i -g @himate/knowledge-cli --registry http://10.143.57.12:4873 --allow-scripts=@himate/knowledge-cli
knowledge setup
# 需要离线 OCR 模型包时
npm i -g @himate/knowledge-models --registry http://10.143.57.12:4873 --allow-scripts=@himate/knowledge-models
```

安装后内容落在：

```
~/.himate/knowledge/
├── knowledge.py         工具包内部入口
├── logs/
├── runtime/
├── governance/
└── tools/deploy/
    ├── deploy.py
    └── models/docling-cpu/
```

平台差异由包内脚本自动处理：

- npm 只注册 `knowledge` 命令。Windows 的 `knowledge.cmd`、`knowledge.ps1` 和 Linux 的 `knowledge` 软链由 npm 生成，位于 npm 的全局命令目录。
- `postinstall` 用 `process.platform` 区分路径分隔符与可执行权限
- 启动器从系统查找 Python 3.10–3.12。`knowledge setup` 用选定的解释器执行 `python -m pip install -r`，在其安装位置补齐工具包锁定的依赖。

Linux 全局安装若提示权限不足，可把 npm 全局目录指到当前用户目录。运行 npm 安装与使用 `knowledge` 采用同一账户：

```bash
npm config set prefix ~/.npm-global
export PATH="$HOME/.npm-global/bin:$PATH"
```

## 4. 使用

```bash
knowledge --version
knowledge -h
knowledge help ingest
knowledge doctor --environment-only --json
knowledge doctor --knowledge-root /path/to/kb --json
knowledge ingest status --knowledge-root /path/to/kb
```

可用 `HIMATE_KNOWLEDGE_PYTHON` 指定解释器的绝对路径。已有虚拟环境可通过指定其中的 Python 来使用。

```bash
export HIMATE_KNOWLEDGE_PYTHON=/usr/bin/python3.11
```

## 5. 更新

更新 CLI 的命令也按 npm 的脚本策略选择。npm 12 安装时使用带授权参数的命令。

```bash
# npm 11 默认策略
npm i -g @himate/knowledge-cli@latest --registry http://10.143.57.12:4873
# npm 12
npm i -g @himate/knowledge-cli@latest --registry http://10.143.57.12:4873 --allow-scripts=@himate/knowledge-cli
```

CLI 安装脚本保留 `logs/` 和 `tools/deploy/models/`。需要继续使用旧版本创建的 `.venv` 时，通过 `HIMATE_KNOWLEDGE_PYTHON` 显式指定其中的解释器。更新后运行 `knowledge doctor --environment-only`，如有新的依赖缺口再运行 `knowledge setup`。

升级到 0.23.0 时，将自动化脚本中的旧命令名 `himate-knowledge` 改为 `knowledge`。

## 6. 注意事项

- 安装时不要加 `--ignore-scripts`，否则文件不会复制到 `~/.himate/knowledge`
- 部分 npm 11 版本会提醒用户检查安装脚本。内网另有脚本策略时，按该策略和客户端支持的参数选择命令
- 模型包安装时会按 `manifest.json` 校验每个分片的字节数与 SHA-256，校验失败会中止安装
- 两个包的安装顺序不限：先装 CLI 或先装模型都可以
- 本机需要可用的 Node.js 和 Python 3.10–3.12。补装依赖时，选定的 Python 需要可用的 pip，且 pip 的安装位置需要允许写入。系统发行版管理 Python 时，按该发行版的策略选择允许安装依赖的解释器。 [宿主环境配置](tools/deploy/README.md#检查或安装宿主运行环境)
- 安装失败可按提示检查本机 `~/.himate/knowledge/logs/` 下的日志。命令输出包含错误原因，便于 OpenFlow 显示处理提示。
- `knowledge setup` 复用 npm 启动器。需要诊断环境时可运行 `knowledge doctor --environment-only --json`，无需选择知识库。
- 模型 npm 包提供工具侧离线模型。知识库启用 `standard` OCR 时，仍为相应知识根准备模型。 [OCR 部署说明](tools/deploy/README.md#为现有知识库准备-ocr)
