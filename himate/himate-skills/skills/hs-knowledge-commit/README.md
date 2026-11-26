# hs-knowledge-commit

## 中文介绍

将已确认的独立领域知识仓全仓提交，并按用户要求通过 `git mm upload . -y` 上传 CodeHub CR。Skill 负责摘要、DTS 交互和领域 Team 模板；固定 Git 执行、校验和本地记录由知识 CLI 负责，MCP 复用同一执行能力。

沿用本轮已确认的知识根与执行端，没有目标时才询问。`knowledge repo status` 读取实际分支、全仓变更、`origin/master..HEAD` 未合入提交数、最新提交正文和 Change-Id，以及历史 DTS。

无未合入提交时，新建提交的正文为：

```text
Description:<中文摘要>
DTS:<用户确认的DTS>

Team:<DOMAIN>
Feature or Bugfix:Feature
```

`DOMAIN` 是仓目录名中 `himate-knowledge-` 后的首段大写，后缀不参与。例如 `himate-knowledge-wifi-xxx` 为 `WIFI`，`himate-knowledge-bluetooth-lab` 为 `BLUETOOTH`。完整正文由 Skill 传入 CLI，CLI 不生成模板。

存在未合入提交时，先回显最新正文和 Change-Id，按用户已确认的方式修改最新一笔：严格使用 `git commit --amend --no-edit` 保留原正文，写请求省略 `message`。DTS 必须由用户提供或确认；历史记录可作为待确认的默认选项，已经明确确认的事项不重复询问。

## 使用方式

MCP 使用已绑定知识根的 `knowledge_repo_status`（输入 `{}`）和 `knowledge_repo_commit`。CLI 使用同一执行端的知识入口：

```sh
knowledge repo status --knowledge-root "<独立知识仓根绝对路径>" --json
knowledge repo commit --knowledge-root "<独立知识仓根绝对路径>" --input "<输入JSON绝对路径>" --json
```

提交 JSON 字段为 `message`（新建时必填）、`dts`、`upload` 和必填的 `approved: true`。后者对应用户已明确授权的本次全仓提交、amend 或上传操作。输入文件需放在已忽略的临时位置。CLI 也支持 `--input -` 读取同一 JSON 对象，不接受任意 Git 参数或目标覆盖字段。

执行器在提交前确保知识仓 `.scratch/` 已忽略，提交成功后将 DTS 记录到 `<知识根>/.scratch/hs-knowledge-commit/dts.json`。状态读取没有写副作用。

根据回执报告实际提交 SHA、create/amend、Change-Id 和上传结果；有 `cr_url` 时原样回显。失败时保留已完成阶段和命令输出，停止，不自动重试。这里不执行同步、回退或分支操作。完整 Agent 流程见 [SKILL.md](SKILL.md)。
