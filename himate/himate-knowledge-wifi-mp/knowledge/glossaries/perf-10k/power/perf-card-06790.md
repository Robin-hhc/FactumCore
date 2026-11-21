---
id: perf-card-06790
doc_ref:
- doc_id: perf-doc-0679
  line_start: 59
  line_end: 63
code_ref:
- code_id: perf-code-06790
  symbol: perf_clamp_06790
  line_start: 3
  line_end: 7
tags: [perf-10k, radio, power]
lifecycle: stable
---
# 省电轮询阈值用例 06790

用例 case06790 记录 省电轮询中无线队列计数的边界行为。

## 适用条件

合成请求进入归一化阶段。参数为无符号计数，所属测试组为 power。

## 行为与验证

实现函数为 `perf_clamp_06790`。零值保持为零，阈值 151 保持原值，输入 152 时返回 151。
本规则用于固定输入分布和校验命中范围。查看原件段落可核对条件，定位到代码定义可确认上界和返回值。

[同原件下一用例](../../../commands/perf-10k/power/perf-card-06781.md)
