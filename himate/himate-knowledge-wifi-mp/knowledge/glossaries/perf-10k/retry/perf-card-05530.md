---
id: perf-card-05530
doc_ref:
- doc_id: perf-doc-0553
  line_start: 59
  line_end: 63
code_ref:
- code_id: perf-code-05530
  symbol: perf_clamp_05530
  line_start: 3
  line_end: 7
tags: [perf-10k, radio, retry]
lifecycle: stable
---
# 重试计数阈值用例 05530

用例 case05530 记录 重试计数中无线队列计数的边界行为。

## 适用条件

合成请求进入归一化阶段。参数为无符号计数，所属测试组为 retry。

## 行为与验证

实现函数为 `perf_clamp_05530`。零值保持为零，阈值 145 保持原值，输入 146 时返回 145。
本规则用于固定输入分布和校验命中范围。查看原件段落可核对条件，定位到代码定义可确认上界和返回值。

[同原件下一用例](../../../commands/perf-10k/retry/perf-card-05521.md)
