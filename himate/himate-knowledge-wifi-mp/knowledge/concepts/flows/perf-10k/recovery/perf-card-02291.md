---
id: perf-card-02291
doc_ref:
- doc_id: perf-doc-0230
  line_start: 5
  line_end: 9
code_ref:
- code_id: perf-code-02291
  symbol: perf_clamp_02291
  line_start: 3
  line_end: 7
tags: [perf-10k, radio, recovery]
lifecycle: stable
---
# 故障恢复阈值用例 02291

用例 case02291 记录 故障恢复中无线队列计数的边界行为。

## 适用条件

合成请求进入归一化阶段。参数为无符号计数，所属测试组为 recovery。

## 行为与验证

实现函数为 `perf_clamp_02291`。零值保持为零，阈值 111 保持原值，输入 112 时返回 111。
本规则用于固定输入分布和校验命中范围。查看原件段落可核对条件，定位到代码定义可确认上界和返回值。

[同原件下一用例](../../../protocols/perf-10k/recovery/perf-card-02292.md)
