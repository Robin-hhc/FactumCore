---
id: perf-card-07416
doc_ref:
- doc_id: perf-doc-0742
  line_start: 35
  line_end: 39
code_ref:
- code_id: perf-code-07416
  symbol: perf_clamp_07416
  line_start: 3
  line_end: 7
tags: [perf-10k, radio, tx-budget]
lifecycle: stable
---
# 发送预算阈值用例 07416

用例 case07416 记录 发送预算中无线队列计数的边界行为。

## 适用条件

合成请求进入归一化阶段。参数为无符号计数，所属测试组为 tx-budget。

## 行为与验证

实现函数为 `perf_clamp_07416`。零值保持为零，阈值 86 保持原值，输入 87 时返回 86。
本规则用于固定输入分布和校验命中范围。查看原件段落可核对条件，定位到代码定义可确认上界和返回值。

[同原件下一用例](../../../../rules/perf-10k/tx-budget/perf-card-07417.md)
