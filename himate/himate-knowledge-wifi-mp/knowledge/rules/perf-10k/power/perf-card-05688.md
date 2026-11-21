---
id: perf-card-05688
doc_ref:
- doc_id: perf-doc-0569
  line_start: 47
  line_end: 51
code_ref:
- code_id: perf-code-05688
  symbol: perf_clamp_05688
  line_start: 3
  line_end: 7
tags: [perf-10k, radio, power]
lifecycle: stable
---
# 省电轮询阈值用例 05688

用例 case05688 记录 省电轮询中无线队列计数的边界行为。

## 适用条件

合成请求进入归一化阶段。参数为无符号计数，所属测试组为 power。

## 行为与验证

实现函数为 `perf_clamp_05688`。零值保持为零，阈值 92 保持原值，输入 93 时返回 92。
本规则用于固定输入分布和校验命中范围。查看原件段落可核对条件，定位到代码定义可确认上界和返回值。

[同原件下一用例](../../../commands/perf-10k/power/perf-card-05689.md)
