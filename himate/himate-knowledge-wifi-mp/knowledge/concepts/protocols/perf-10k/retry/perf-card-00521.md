---
id: perf-card-00521
doc_ref:
- doc_id: perf-doc-0053
  line_start: 5
  line_end: 9
code_ref:
- code_id: perf-code-00521
  symbol: perf_clamp_00521
  line_start: 3
  line_end: 7
tags: [perf-10k, radio, retry]
lifecycle: stable
---
# 重试计数阈值用例 00521

用例 case00521 记录 重试计数中无线队列计数的边界行为。

## 适用条件

合成请求进入归一化阶段。参数为无符号计数，所属测试组为 retry。

## 行为与验证

实现函数为 `perf_clamp_00521`。零值保持为零，阈值 150 保持原值，输入 151 时返回 150。
本规则用于固定输入分布和校验命中范围。查看原件段落可核对条件，定位到代码定义可确认上界和返回值。

[同原件下一用例](../../../../rules/perf-10k/retry/perf-card-00522.md)
