---
id: perf-card-09909
doc_ref:
- doc_id: perf-doc-0991
  line_start: 53
  line_end: 57
code_ref:
- code_id: perf-code-09909
  symbol: perf_clamp_09909
  line_start: 3
  line_end: 7
tags: [perf-10k, radio, rx-queue]
lifecycle: stable
---
# 接收队列阈值用例 09909

用例 case09909 记录 接收队列中无线队列计数的边界行为。

## 适用条件

合成请求进入归一化阶段。参数为无符号计数，所属测试组为 rx-queue。

## 行为与验证

实现函数为 `perf_clamp_09909`。零值保持为零，阈值 137 保持原值，输入 138 时返回 137。
本规则用于固定输入分布和校验命中范围。查看原件段落可核对条件，定位到代码定义可确认上界和返回值。

[同原件下一用例](../../../commands/perf-10k/rx-queue/perf-card-09910.md)
