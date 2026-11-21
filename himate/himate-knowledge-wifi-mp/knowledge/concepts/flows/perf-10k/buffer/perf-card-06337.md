---
id: perf-card-06337
doc_ref:
- doc_id: perf-doc-0634
  line_start: 41
  line_end: 45
code_ref:
- code_id: perf-code-06337
  symbol: perf_clamp_06337
  line_start: 3
  line_end: 7
tags: [perf-10k, radio, buffer]
lifecycle: stable
---
# 缓冲容量阈值用例 06337

用例 case06337 记录 缓冲容量中无线队列计数的边界行为。

## 适用条件

合成请求进入归一化阶段。参数为无符号计数，所属测试组为 buffer。

## 行为与验证

实现函数为 `perf_clamp_06337`。零值保持为零，阈值 169 保持原值，输入 170 时返回 169。
本规则用于固定输入分布和校验命中范围。查看原件段落可核对条件，定位到代码定义可确认上界和返回值。

[同原件下一用例](../../../protocols/perf-10k/buffer/perf-card-06338.md)
