---
id: perf-card-03339
doc_ref:
- doc_id: perf-doc-0334
  line_start: 53
  line_end: 57
code_ref:
- code_id: perf-code-03339
  symbol: perf_clamp_03339
  line_start: 3
  line_end: 7
tags: [perf-10k, radio, buffer]
lifecycle: stable
---
# 缓冲容量阈值用例 03339

用例 case03339 记录 缓冲容量中无线队列计数的边界行为。

## 适用条件

合成请求进入归一化阶段。参数为无符号计数，所属测试组为 buffer。

## 行为与验证

实现函数为 `perf_clamp_03339`。零值保持为零，阈值 248 保持原值，输入 249 时返回 248。
本规则用于固定输入分布和校验命中范围。查看原件段落可核对条件，定位到代码定义可确认上界和返回值。

[同原件下一用例](../../../concepts/entities/perf-10k/buffer/perf-card-03340.md)
