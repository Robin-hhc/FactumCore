# 候选组织

`.build/cards/` 中保存完整最终卡稿；相对路径用于正式 `knowledge/` 下的目标路径。更新沿用原路径与卡 ID，新卡选择清楚的主题名称。

需要移除旧文件时，在 `.build/changes.json` 的 `delete` 数组列出相对知识根的 `knowledge/...md` 路径。只有本轮明确移除的旧文件进入清单；退役也可保留完整旧卡并写明原因与替代入口。

合并或拆分涉及的主卡、旧卡和链接一次写完整，不能让 P5 临时猜语义。正式卡 ID、来源 ID 和引用定位使用实际数据，格式见知识根 `governance/specs/cards.md`。

需登记新增代码来源时，按知识根 `governance/specs/sources.md` 的登记参数调用CLI；其中说明路径基准及GB18030编码字段，不猜参数或来源ID。
