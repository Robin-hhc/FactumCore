---
id: perf-card-08456
doc_ref:
- doc_id: perf-doc-0846
  line_start: 35
  line_end: 39
code_ref:
- code_id: perf-code-08456
  symbol: perf_clamp_08456
  line_start: 3
  line_end: 7
tags: [perf-10k, radio, scheduler]
lifecycle: stable
---
# 调度批次阈值用例 08456

用例 case08456 记录 调度批次中无线队列计数的边界行为。

## 适用条件

合成请求进入归一化阶段。参数为无符号计数，所属测试组为 scheduler。

## 行为与验证

实现函数为 `perf_clamp_08456`。零值保持为零，阈值 87 保持原值，输入 88 时返回 87。
本规则用于固定输入分布和校验命中范围。查看原件段落可核对条件，定位到代码定义可确认上界和返回值。

[同原件下一用例](../../../concepts/entities/perf-10k/scheduler/perf-card-08457.md)
