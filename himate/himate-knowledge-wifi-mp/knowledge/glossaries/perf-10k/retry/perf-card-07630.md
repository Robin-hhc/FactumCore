---
id: perf-card-07630
doc_ref:
- doc_id: perf-doc-0763
  line_start: 59
  line_end: 63
code_ref:
- code_id: perf-code-07630
  symbol: perf_clamp_07630
  line_start: 3
  line_end: 7
tags: [perf-10k, radio, retry]
lifecycle: stable
---
# 重试计数阈值用例 07630

用例 case07630 记录 重试计数中无线队列计数的边界行为。

## 适用条件

合成请求进入归一化阶段。参数为无符号计数，所属测试组为 retry。

## 行为与验证

实现函数为 `perf_clamp_07630`。零值保持为零，阈值 238 保持原值，输入 239 时返回 238。
本规则用于固定输入分布和校验命中范围。查看原件段落可核对条件，定位到代码定义可确认上界和返回值。

[同原件下一用例](../../../commands/perf-10k/retry/perf-card-07621.md)
