---
name: hs-knowledge-source
description: 扫描一个变化文档或巡检指定代码文件，获取来源ID、关联卡和本轮材料；用于P1。
---

# 单文件来源准备

在实际知识根执行命令，Linux 使用 `sh ./knowledge.sh`，Windows 使用 `.\knowledge.cmd`；已注册入口可直接用 `knowledge`。位置由 Workflow 首节点确认，独立使用时从当前工作区 `AGENTS.md`、`config.yml` 获取。

## 执行

运行 `knowledge ingest scan --json`；指定来源时加 `--source` 和实际路径或来源 ID。该命令初始化本轮 `.build`，以内容 hash 找一份新增、修改或删除来源，并通过数据库反查关联卡。

- `prepared`：交接返回的 task、文件副本、来源 ID 和关联卡列表，连同实际执行端、知识根及已验证的 CLI 命令前缀进入 P2；后续节点沿用该解释器。
- `unchanged`：本次范围无待办，结束。
- 读取或运行失败：说明具体错误，不能当作无变化或删除。

巡检已选文件时完整采用其 `source_id`，不改成另一个来源。P5 失败后留在 P5 重试，不重新扫描或清暂存。原件只读。

新增主题由 P2 判断；脚本反查只提供已有引用候选。需要来源登记、关系查询或旧版时，读[来源操作](references/materials.md)。
