---
id: perf-card-00316
doc_ref:
- doc_id: perf-doc-0032
  line_start: 35
  line_end: 39
code_ref:
- code_id: perf-code-00316
  symbol: perf_clamp_00316
  line_start: 3
  line_end: 7
tags: [perf-10k, radio, tx-budget]
lifecycle: stable
---
# 发送预算阈值用例 00316

用例 case00316 记录 发送预算中无线队列计数的边界行为。

## 适用条件

合成请求进入归一化阶段。参数为无符号计数，所属测试组为 tx-budget。

## 行为与验证

实现函数为 `perf_clamp_00316`。零值保持为零，阈值 151 保持原值，输入 152 时返回 151。
本规则用于固定输入分布和校验命中范围。查看原件段落可核对条件，定位到代码定义可确认上界和返回值。

[同原件下一用例](../../../flows/perf-10k/tx-budget/perf-card-00317.md)
