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

Windows 和 Linux 使用**同一条命令**，不需要区分平台：

```bash
npm i -g @himate/knowledge-cli --registry http://10.143.57.12:4873 --allow-scripts=@himate/knowledge-cli
knowledge setup
# 需要离线 OCR 模型包时
npm i -g @himate/knowledge-models --registry http://10.143.57.12:4873 --allow-scripts=@himate/knowledge-models
```

安装后内容落在：

```
~/.himate/knowledge/
├── knowledge.py
├── knowledge.cmd / knowledge.sh
├── .venv/
├── logs/
├── runtime/
├── governance/
└── tools/deploy/
    ├── deploy.py
    └── models/docling-cpu/
```

平台差异由包内脚本自动处理：

- npm 根据 `bin` 字段自动生成 Windows 的 `knowledge.cmd` / `knowledge.ps1`，Linux 生成软链
- `postinstall` 用 `process.platform` 区分路径分隔符与可执行权限
- 启动器优先使用已准备的虚拟环境。首次运行从系统查找受支持的 Python 3.10–3.12，`knowledge setup` 用它创建专用环境并安装锁定依赖。

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

同时注册了长别名 `himate-knowledge`，与 `knowledge` 完全等价。

可用 `HIMATE_KNOWLEDGE_PYTHON` 指定解释器。指定已有虚拟环境时沿用该环境，指定系统 Python 时用于初始化专用环境。

```bash
export HIMATE_KNOWLEDGE_PYTHON=/usr/bin/python3.11
```

## 5. 更新

只更新 CLI，模型不动：

```bash
npm i -g @himate/knowledge-cli@latest --registry http://10.143.57.12:4873 --allow-scripts=@himate/knowledge-cli
```

CLI 安装脚本保留 `.venv/`、`logs/` 和 `tools/deploy/models/`。更新后运行 `knowledge doctor --environment-only`，如有新的依赖缺口再运行 `knowledge setup`。

## 6. 注意事项

- 安装时不要加 `--ignore-scripts`，否则文件不会复制到 `~/.himate/knowledge`
- npm 11 默认拦截依赖的安装脚本，安装命令需带 `--allow-scripts=<包名>`（见上文），否则只会看到警告、文件不会复制
- 模型包安装时会按 `manifest.json` 校验每个分片的字节数与 SHA-256，校验失败会中止安装
- 两个包的安装顺序不限：先装 CLI 或先装模型都可以
- 本机需要可用的 Node.js 和支持创建虚拟环境的 Python 3.10–3.12。Debian 或 Ubuntu 缺少 `ensurepip` 时，安装报错会提示与所选 Python 版本配套的 `venv` 系统包。
- 安装失败可按提示检查本机 `~/.himate/knowledge/logs/` 下的日志。命令输出包含错误原因，便于 OpenFlow 显示处理提示。
- `knowledge setup` 复用 npm 启动器。需要诊断环境时可运行 `knowledge doctor --environment-only --json`，无需选择知识库。
- 模型 npm 包提供工具侧离线模型。知识库启用 `standard` OCR 时，仍为相应知识根准备模型。 [OCR 部署说明](tools/deploy/README.md#为现有知识库准备-ocr)
