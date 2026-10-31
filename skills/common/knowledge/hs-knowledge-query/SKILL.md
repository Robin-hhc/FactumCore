---
name: hs-knowledge-query
description: 按关键词和可选标签检索正式知识卡，精读正文并沿来源核对答案。
---

# 搜索、精读与回源

在实际知识根执行命令，Linux 使用 `sh ./knowledge.sh`，Windows 使用 `.\knowledge.cmd`；已注册入口可直接用 `knowledge`。位置由 Workflow 首节点确认，独立使用时从当前工作区 `AGENTS.md`、`config.yml` 获取。

## 检索

```sh
knowledge search "关键词" --json
knowledge read CARD_ID --json
```

搜索返回完整卡的相关候选，不认证当前适用或已实现。需要标签时用 `--input`，检索整卡退役资料时用 `--include-deprecated`；请求和结果字段见[公开 API](references/public-api.md)。

先搜索，再读相关卡与必要来源，按问题核对正文条件、版本、依据性质及缺口。设计要求保持设计属性，代码行为和测量结论须有对应实际依据；卡片命中、stable 状态或代码定位不代替证明。回答附卡 ID、来源和未解决缺口。

空命中时检查关键词、显式标签、退役状态、截断和诊断，再有依据地调整检索。旧 draft 可按 ID 阅读，不自动升为正式可搜状态。运行失败不能当作有效空结果。

使用本次命令返回值及 `report_ref`；每次搜索报告独立保存在 `artifacts/query/`。查询不读写入库 `.build`，不入库、不初始化代码图谱。显式保存输出也使用 `artifacts/query/`。

[公开 API](references/public-api.md)说明查询字段、旧参数错误及来源路径。
