---
id: perf-card-04103
doc_ref:
- doc_id: perf-doc-0411
  line_start: 17
  line_end: 21
code_ref:
- code_id: perf-code-04103
  symbol: perf_clamp_04103
  line_start: 3
  line_end: 7
tags: [perf-10k, radio, rx-queue]
lifecycle: stable
---
# 接收队列阈值用例 04103

用例 case04103 记录 接收队列中无线队列计数的边界行为。

## 适用条件

合成请求进入归一化阶段。参数为无符号计数，所属测试组为 rx-queue。

## 行为与验证

实现函数为 `perf_clamp_04103`。零值保持为零，阈值 39 保持原值，输入 40 时返回 39。
本规则用于固定输入分布和校验命中范围。查看原件段落可核对条件，定位到代码定义可确认上界和返回值。

[同原件下一用例](../../../flows/perf-10k/rx-queue/perf-card-04104.md)
