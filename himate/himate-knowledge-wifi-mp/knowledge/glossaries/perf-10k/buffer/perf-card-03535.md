---
id: perf-card-03535
doc_ref:
- doc_id: perf-doc-0354
  line_start: 29
  line_end: 33
code_ref:
- code_id: perf-code-03535
  symbol: perf_clamp_03535
  line_start: 3
  line_end: 7
tags: [perf-10k, radio, buffer]
lifecycle: stable
---
# 缓冲容量阈值用例 03535

用例 case03535 记录 缓冲容量中无线队列计数的边界行为。

## 适用条件

合成请求进入归一化阶段。参数为无符号计数，所属测试组为 buffer。

## 行为与验证

实现函数为 `perf_clamp_03535`。零值保持为零，阈值 94 保持原值，输入 95 时返回 94。
本规则用于固定输入分布和校验命中范围。查看原件段落可核对条件，定位到代码定义可确认上界和返回值。

[同原件下一用例](../../../concepts/entities/perf-10k/buffer/perf-card-03536.md)
