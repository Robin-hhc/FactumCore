---
id: perf-card-06451
doc_ref:
- doc_id: perf-doc-0646
  line_start: 5
  line_end: 9
code_ref:
- code_id: perf-code-06451
  symbol: perf_clamp_06451
  line_start: 3
  line_end: 7
tags: [perf-10k, radio, scheduler]
lifecycle: stable
---
# 调度批次阈值用例 06451

用例 case06451 记录 调度批次中无线队列计数的边界行为。

## 适用条件

合成请求进入归一化阶段。参数为无符号计数，所属测试组为 scheduler。

## 行为与验证

实现函数为 `perf_clamp_06451`。零值保持为零，阈值 115 保持原值，输入 116 时返回 115。
本规则用于固定输入分布和校验命中范围。查看原件段落可核对条件，定位到代码定义可确认上界和返回值。

[同原件下一用例](../../../commands/perf-10k/scheduler/perf-card-06452.md)
