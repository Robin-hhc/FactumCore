# 独立代码引用审计

用户明确要一份只读引用报告时使用；不会自动执行入库或推进巡检成功基线。

```text
python K/knowledge.py maintain --action audit-references --input REQUEST.json --json
```

输入 `operation_id`，可选 K 内的 `lint_report_ref`。提供的报告须为当前正式库的 formal/full 结果；报告缺失、已过时或不完整时保留缺口，本动作不代跑lint。

结果为 `reported`，读取 `audit_ref/report_ref`、`complete`、`status`、`counts`。`status` 的 `passed/needs_review/incomplete` 表示观察结论；命令成功只说明报告生成。

报告覆盖正式卡全部代码来源，包括未被Claim采用的元数据引用，分别列出旧快照/定位、当前字节、符号导航及材料缺口。current的实现依据变化交入库复核；guidance导航仍resolved时，不因整文件字节变化制造导航修复义务；historical仍按固定历史依据判断。无法恢复、读取或唯一定位须明确说明。

展示本次实际返回的Markdown报告，宿主产物位置用执行端K解析后的 `report_ref`，不拿默认文件名或模板代替。文本截断时保留报告中的截断说明。源码、卡、来源锁、事件、水位及活动索引不改变；需要修订时附实际受影响卡和报告引用，交用户或已授权的入库任务。
