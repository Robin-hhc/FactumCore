---
id: perf-card-09013
doc_ref:
- doc_id: perf-doc-0902
  line_start: 17
  line_end: 21
code_ref:
- code_id: perf-code-09013
  symbol: perf_clamp_09013
  line_start: 3
  line_end: 7
tags: [perf-10k, radio, tx-budget]
lifecycle: stable
---
# 发送预算阈值用例 09013

用例 case09013 记录 发送预算中无线队列计数的边界行为。

## 适用条件

合成请求进入归一化阶段。参数为无符号计数，所属测试组为 tx-budget。

## 行为与验证

实现函数为 `perf_clamp_09013`。零值保持为零，阈值 94 保持原值，输入 95 时返回 94。
本规则用于固定输入分布和校验命中范围。查看原件段落可核对条件，定位到代码定义可确认上界和返回值。

[同原件下一用例](../../../commands/perf-10k/tx-budget/perf-card-09014.md)
