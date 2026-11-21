---
id: perf-card-08056
doc_ref:
- doc_id: perf-doc-0806
  line_start: 35
  line_end: 39
code_ref:
- code_id: perf-code-08056
  symbol: perf_clamp_08056
  line_start: 3
  line_end: 7
tags: [perf-10k, radio, scheduler]
lifecycle: stable
---
# 调度批次阈值用例 08056

用例 case08056 记录 调度批次中无线队列计数的边界行为。

## 适用条件

合成请求进入归一化阶段。参数为无符号计数，所属测试组为 scheduler。

## 行为与验证

实现函数为 `perf_clamp_08056`。零值保持为零，阈值 10 保持原值，输入 11 时返回 10。
本规则用于固定输入分布和校验命中范围。查看原件段落可核对条件，定位到代码定义可确认上界和返回值。

[同原件下一用例](../../../glossaries/perf-10k/scheduler/perf-card-08057.md)
