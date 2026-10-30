# 巡检报告说明

显式调用 `audit-references` 并展示它返回的实际 Markdown；不要用旧节点结果模板代替真实引用报告。保留原固定检查结果及其时点，缺报告或正式文件已变化必须说明。逐引用列出实际卡、Claim、来源快照、代码文件、旧定位、旧／当前 hash 和可恢复旧片段；没有 Claim 采用的元数据引用也要保留。

声明 code_ref 时，另列 code_navigation 的状态和实际当前位置。变化的 current 引用仍按现有代码依据限制交人手动转入 ingest；guidance 符号仍唯一可定位时，不因整文件 hash 不同要求修卡；missing／ambiguous／unavailable 分别保留问题及缺口。historical 保持历史用途，未声明符号不虚构导航通过；活动旧卡缺符号按固定 lint／CI 的 CODE_REF_REQUIRED 交 ingest 补齐，历史恢复及 deprecated 卡保留兼容。未授权、不可读、缺原版和观察期间变化均写成实际缺口，不能补记通过。报告只提供修订建议和可复制的手动 ingest 提示词，不替换旧行号、hash、卡或来源锁。

OpenFlow 交棒时，必须使用本次实际返回的 `report_ref`，按执行端 K 解析为实际文件路径，再显式提供 artifact 实例的 `location.path`。默认位置只声明 `kind: markdown_file`；不能用固定默认路径、模板正文或调用端副本替代真实报告。
