---
name: hs-knowledge-view-materialize
description: 按本轮编辑计划和领域模板撰写或修订完整候选卡；用于P3。
---

# 按计划写完整卡

在实际知识根执行命令，Linux 使用 `sh ./knowledge.sh`，Windows 使用 `.\knowledge.cmd`；已注册入口可直接用 `knowledge`。位置由 Workflow 首节点确认，独立使用时从当前工作区 `AGENTS.md`、`config.yml` 获取。

## 成稿

读取 `.build/plan.md` 的 `cards` 清单、本次材料和必要旧卡，选择知识根 `governance/templates/` 中合适模板，按既定 ID 和路径写完整 Markdown 候选。

将计划 `path` 的 `knowledge/` 前缀替换为 `.build/cards/`，在对应位置写卡；不自行重选目录，不在卡头增加 `path`。清单为 `cards: []` 时不生成候选。

- 按主题融合新旧知识，保留仍成立的结论、适用条件和其它来源。
- 普通更新沿用卡 ID；合并、拆分、退役写好旧卡去向与替代入口。
- 卡头填写 `id/doc_ref/code_ref`，引用实际来源 ID 和对应定位；需新增来源 ID 时使用 `knowledge source register --input`。
- 设计要求与实现事实分清，代码结论核对实际代码；插行时更新需要调整的定位。

必须移除的旧卡文件列入可选 `.build/changes.json`；具体格式见[候选组织](references/request.md)。正式 `knowledge/` 在本步保持不变。

表达、格式或偏离计划的路径拼写问题直接改稿；计划中的 ID、路径或实质决定需要改变时，先回 P2 更新短计划。完整稿交 P4，修改后的稿重新审阅。
