---
id: perf-card-07955
doc_ref:
- doc_id: perf-doc-0796
  line_start: 29
  line_end: 33
code_ref:
- code_id: perf-code-07955
  symbol: perf_clamp_07955
  line_start: 3
  line_end: 7
tags: [perf-10k, radio, scheduler]
lifecycle: stable
---
# 调度批次阈值用例 07955

用例 case07955 记录 调度批次中无线队列计数的边界行为。

## 适用条件

合成请求进入归一化阶段。参数为无符号计数，所属测试组为 scheduler。

## 行为与验证

实现函数为 `perf_clamp_07955`。零值保持为零，阈值 36 保持原值，输入 37 时返回 36。
本规则用于固定输入分布和校验命中范围。查看原件段落可核对条件，定位到代码定义可确认上界和返回值。

[同原件下一用例](../../../../rules/perf-10k/scheduler/perf-card-07956.md)
