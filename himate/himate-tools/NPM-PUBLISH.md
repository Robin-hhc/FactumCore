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
npm i -g @himate/knowledge-cli --registry http://10.143.57.12:4873
npm i -g @himate/knowledge-models --registry http://10.143.57.12:4873
```

安装后内容落在：

```
~/.himate/knowledge/
├── knowledge.py
├── knowledge.cmd / knowledge.sh
├── runtime/
├── governance/
└── tools/deploy/
    ├── deploy.py
    └── models/docling-cpu/
```

平台差异由包内脚本自动处理：

- npm 根据 `bin` 字段自动生成 Windows 的 `knowledge.cmd` / `knowledge.ps1`，Linux 生成软链
- `postinstall` 用 `process.platform` 区分路径分隔符与可执行权限
- 启动器按平台探测 Python：Windows 依次试 `py -3.11`、`py -3.12`、`py -3.10`、`python`、`python3`；Linux 依次试 `python3`、`python`、`python3.11`、`python3.12`、`python3.10`

Linux 全局安装若提示权限不足，使用 `sudo`，或先把 npm 全局目录指到用户目录：

```bash
npm config set prefix ~/.npm-global
export PATH="$HOME/.npm-global/bin:$PATH"
```

## 4. 使用

```bash
knowledge --version
knowledge -h
knowledge help ingest
knowledge status --knowledge-root /path/to/kb
```

同时注册了长别名 `himate-knowledge`，与 `knowledge` 完全等价。

指定 Python 解释器：

```bash
export HIMATE_KNOWLEDGE_PYTHON=/usr/bin/python3.11
```

## 5. 更新

只更新 CLI，模型不动：

```bash
npm i -g @himate/knowledge-cli@latest --registry http://10.143.57.12:4873
```

CLI 安装脚本只覆盖代码目录，不会删除 `tools/deploy/models/`。

## 6. 注意事项

- 安装时不要加 `--ignore-scripts`，否则文件不会复制到 `~/.himate/knowledge`
- 模型包安装时会按 `manifest.json` 校验每个分片的字节数与 SHA-256，校验失败会中止安装
- 两个包的安装顺序不限：先装 CLI 或先装模型都可以
- 首次安装后仍需按需安装 Python 依赖：`knowledge doctor` 会报告缺失项
