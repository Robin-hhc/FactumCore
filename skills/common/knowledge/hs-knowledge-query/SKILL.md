---
name: hs-knowledge-query
description: 按问题用途与实际范围检索正式知识，精读命中卡并沿来源核对答案。
---

# 搜索、精读与回源

在实际知识根执行命令，Linux 使用 `sh ./knowledge.sh`，Windows 使用 `.\knowledge.cmd`；已注册入口可直接用 `knowledge`。位置由 Workflow 首节点确认，独立使用时从当前工作区 `AGENTS.md`、`config.yml` 获取。

## 检索

```sh
knowledge search "关键词" --purpose guidance --json
knowledge read CARD_ID --json
```

按问题选择用途：背景／设计用 `guidance`，当前适用结论用 `current`，实现事实用 `implementation`，旧版用 `historical`。复杂条件以 `--input` 提供 `query/purpose/context/top_k`；只填用户问题和材料支持的条件。

先搜索，再读相关卡与必要来源。代码行为和条件须实际核对，卡片或定位链接不代替代码依据。结果附卡 ID、来源和未解决缺口。

空命中时先检查用途、范围和诊断，再有依据地调整关键词；不猜条件凑命中。运行失败不能当作有效空结果。

使用本次命令返回值及 `report_ref`；每次搜索报告独立保存在 `artifacts/query/`。查询不读写入库 `.build`，不入库、不初始化代码图谱。显式保存输出也使用 `artifacts/query/`。

[公开 API](references/public-api.md)说明用途、条件和来源路径。
