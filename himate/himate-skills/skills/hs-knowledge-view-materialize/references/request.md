# 候选组织

`.build/cards/` 中保存 `.build/plan.md` 的 `cards` 清单对应的完整最终卡稿。计划 `path` 的 `knowledge/` 前缀替换为 `.build/cards/` 即为草稿位置，例如 `knowledge/concepts/flows/radio-flow.md` 对应 `.build/cards/concepts/flows/radio-flow.md`；卡头使用清单中的 `id`，不增加 `path` 字段。P3 不另选路径；漏卡、多卡、ID 或落位不符由 P4 的 `ingest check` 报出。

实际稿件偏离既定路径时在 P3 修正。计划决定本身要改变时回 P2，同轮更新清单和自然语言计划。

需要移除旧文件时，在 `.build/changes.json` 的 `delete` 数组列出相对知识根的 `knowledge/...md` 路径。只有本轮明确移除的旧文件进入清单；退役也可保留完整旧卡并写明原因与替代入口。

合并或拆分涉及的主卡、旧卡和链接一次写完整，写明去向，并修复受影响的入链和锚点。
