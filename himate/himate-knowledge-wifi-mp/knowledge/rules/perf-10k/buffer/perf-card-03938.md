---
id: perf-card-03938
doc_ref:
- doc_id: perf-doc-0394
  line_start: 47
  line_end: 51
code_ref:
- code_id: perf-code-03938
  symbol: perf_clamp_03938
  line_start: 3
  line_end: 7
tags: [perf-10k, radio, buffer]
lifecycle: stable
---
# 缓冲容量阈值用例 03938

用例 case03938 记录 缓冲容量中无线队列计数的边界行为。

## 适用条件

合成请求进入归一化阶段。参数为无符号计数，所属测试组为 buffer。

## 行为与验证

实现函数为 `perf_clamp_03938`。零值保持为零，阈值 222 保持原值，输入 223 时返回 222。
本规则用于固定输入分布和校验命中范围。查看原件段落可核对条件，定位到代码定义可确认上界和返回值。

[同原件下一用例](../../../commands/perf-10k/buffer/perf-card-03939.md)
