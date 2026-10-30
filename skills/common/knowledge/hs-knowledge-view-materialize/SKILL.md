---
name: hs-knowledge-view-materialize
description: 按已定内容计划保存完整候选稿、来源登记及处置预览；用于入库和巡检的P3成稿与稿件修订。
---

# 保存完整候选稿

## 目标与输入

按本次 `semantic_plan_ref` 和它采用的材料，写出完整卡片并一次保存可审阅的候选视图。P3 落实作者决定；结论或归卡尚不明确时回 P2，缺原文或代码材料时回 source。

复用已知知识根和执行端；缺位置时读当前工作区 `AGENTS.md`、`config.yml`，必要时询问用户。首次读知识根 `AGENTS.md`；以下在该目录执行，POSIX 用 `sh ./knowledge.sh`。

## 成稿与保存

1. 按 P2 决定准备本批完整卡稿，明确合并／拆分／退役及旧 Claim 去向，采用知识根 `governance/specs/cards.md` 的格式。
2. 保留实际来源、快照、定位及 Claim 引用。活动卡引用代码时，根据本次源码填写支持的 `code_ref`；纯文档不添加虚构代码入口，旧快照定位不随当前行号改写。
3. 用实际稿件引用构造请求，一次保存本批卡、导航、来源锁、处置预览和输入绑定。字段与六类动作见[成稿请求](references/request.md#成稿请求)。

```powershell
.\knowledge.cmd view-materialize --input REQUEST.json --json
```

`ready` 时将真实 `view_ref` 及相关引用交 P4。正式知识此时不变；仅记录批也有明确空写集和处置预览。

## 修订与失败

已有候选需改稿时，使用新操作、真实 `previous_view_ref` 和 `revision_reason` 调用 `--action revise`。仅改稿可以采用该视图绑定的未变计划与材料；补料或重判后采用对应新版本，见[修订](references/request.md#修订)。新稿重新交 P4。

同操作重入只读取仍匹配的已保存结果，不重新生成内容。失败保留实际诊断：缺料回 source，判断问题回 P2；输入漂移先刷新相应输入，不覆盖旧工件。计划已冻结但尚无 view 的补料若遇绑定阻断，保留停点，不编造前序视图继续。

本步不独立审阅、不运行整库质量检查，也不发布、启用索引或提交 Git。需要只读查看已保存候选时，用[describe](references/request.md#只读描述)。
