---
name: hs-knowledge-commit
description: 将独立领域知识仓的改动提交，并按用户要求上传 CodeHub CR；负责提交摘要、DTS 确认和领域 Team 模板，通过知识 CLI 或 MCP 执行。
---

# 知识仓上库

沿用用户指定、宿主绑定或本轮已确认的知识根和执行端；上下文没有目标时才询问缺少的知识根或执行端。实际知识根必须是独立 Git 仓根，不能按 Skill 安装位置、开发仓路径或目录中的 WiFi 示例推断目标。上库覆盖这个仓的全部变更，执行器使用 `git add .`。

当前会话提供 `knowledge_repo_status` 和 `knowledge_repo_commit` 时，使用同一知识根绑定的 MCP。采用 CLI 时，在已确认的执行端使用 `knowledge` 入口，每次传入同一绝对 `--knowledge-root`。首次单独使用 CLI 时，读取知识根的 `AGENTS.md`、`config.yml`，用 `knowledge doctor --knowledge-root "<知识根绝对路径>" --json` 核对目标和版本。明确缺少 CLI、启动入口或运行依赖时，用 `hs-knowledge-setup` 修复同一执行端，复查后继续原调用方式。绑定、连接或业务错误按实际回执处理。

## 读取状态与确认

先调用 `knowledge_repo_status`，输入 `{}`。CLI 对应：

```sh
knowledge repo status --knowledge-root "<知识根绝对路径>" --json
```

以 `status=ok`、`phase=ready` 的回执核对 `data.knowledge_root`、`branch`、`pending_commits` 和 `changes`；向用户回显实际变更集。`pending_commits` 按 `origin/master..HEAD` 计算，不能换成其他基线。存在未合入提交时，还要回显 `latest_commit.message` 原正文与 `latest_commit.change_id`，说明本次将修改最新一笔并保留这些内容。

DTS 只能来自用户本轮提供的值、上下文中已明确确认的值，或经用户确认沿用的 `data.dts` 历史记录。记录不是自动授权：尚未确认时，用中文提供「沿用上次 <DTS>」和「输入新单号」；没有可用值时索取单号，不编造。用户已经明确提供或确认的本次 DTS 不重复询问。

确认本次全仓提交、是否上传，以及存在未合入提交时的 amend 方式。只问仍缺的事项；用户已明确授权的操作直接沿用，在写请求中传 `approved: true`。未获本次操作授权时不能以该字段代替确认。

## 新建提交与修改最新提交

`pending_commits == 0` 时，由本 Skill 根据实际变更生成一行中文摘要，并组成完整提交正文：

```text
Description:<中文摘要>
DTS:<用户确认的DTS>

Team:<DOMAIN>
Feature or Bugfix:Feature
```

保留 DTS 后的空行。`DOMAIN` 取实际仓目录名中 `himate-knowledge-` 后的首段并转大写：`himate-knowledge-wifi-mp`、`himate-knowledge-wifi-xxx` 都是 `WIFI`，`himate-knowledge-bluetooth-lab-xxx` 是 `BLUETOOTH`；后缀不参与。目录名无法确定 domain 时询问 Team，不固定成 WIFI。摘要和模板由 Skill 生成，CLI 只接收完整 `message` 原文。

`pending_commits > 0` 时，执行器必须使用 `git commit --amend --no-edit`，保留最新提交原正文与 Change-Id。此时不生成或传入新 `message`，也不按本次摘要、DTS 或 Team 重写旧正文；本次确认的 DTS 可作为本地记录单独传入。

调用 `knowledge_repo_commit`，输入仅使用：

- `message`：新建提交时的完整多行正文；amend 时省略。
- `dts`：本次已确认的 DTS，用于本地记录。
- `upload`：布尔值；只提交为 `false`，用户要求提交并上传为 `true`。
- `approved`：本次操作已获用户明确授权时为 `true`，必填。

使用 CLI 时，将同一 JSON 对象写入输入文件，或通过标准输入传入；不要用 shell 拼接多行正文：

```sh
knowledge repo commit --knowledge-root "<知识根绝对路径>" --input "<输入JSON绝对路径>" --json
knowledge repo commit --knowledge-root "<知识根绝对路径>" --input - --json
```

MCP 的知识根来自既有绑定，业务输入不增加 root、argv、命令或 DTS 路径覆盖字段。CLI/MCP 负责固定 Git 命令、`.scratch/` 忽略检查和成功后的 `.scratch/hs-knowledge-commit/dts.json` 记录；普通状态读取不写文件。输入文件放到已忽略的临时位置，避免被全仓暂存。

## 结果与失败

核对 JSON 的业务状态和阶段，报告实际 `mode`、`commit_sha`、Change-Id 及是否上传。上传由执行器运行 `git mm upload . -y`，仅原样回显回执中的 `cr_url`，不自行拼接 CodeHub 域名或 CR 链接。

失败时报告已完成阶段、本地提交 SHA，以及 `commands` 中实际 stdout/stderr 和诊断，停止，不自动重试提交或上传。上传输出未能解析出 CR 链接时保留失败回执和原输出，不把它当成已完成上传。不执行 `pull`、`push`、`rebase`、`reset` 或分支切换。
