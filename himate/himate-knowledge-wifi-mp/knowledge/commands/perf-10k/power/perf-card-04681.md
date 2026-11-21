---
id: perf-card-04681
doc_ref:
- doc_id: perf-doc-0469
  line_start: 5
  line_end: 9
code_ref:
- code_id: perf-code-04681
  symbol: perf_clamp_04681
  line_start: 3
  line_end: 7
tags: [perf-10k, radio, power]
lifecycle: stable
---
# 省电轮询阈值用例 04681

用例 case04681 记录 省电轮询中无线队列计数的边界行为。

## 适用条件

合成请求进入归一化阶段。参数为无符号计数，所属测试组为 power。

## 行为与验证

实现函数为 `perf_clamp_04681`。零值保持为零，阈值 154 保持原值，输入 155 时返回 154。
本规则用于固定输入分布和校验命中范围。查看原件段落可核对条件，定位到代码定义可确认上界和返回值。

[同原件下一用例](../../../runbooks/perf-10k/power/perf-card-04682.md)
