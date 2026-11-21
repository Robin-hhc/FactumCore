---
id: perf-card-04227
doc_ref:
- doc_id: perf-doc-0423
  line_start: 41
  line_end: 45
code_ref:
- code_id: perf-code-04227
  symbol: perf_clamp_04227
  line_start: 3
  line_end: 7
tags: [perf-10k, radio, retry]
lifecycle: stable
---
# 重试计数阈值用例 04227

用例 case04227 记录 重试计数中无线队列计数的边界行为。

## 适用条件

合成请求进入归一化阶段。参数为无符号计数，所属测试组为 retry。

## 行为与验证

实现函数为 `perf_clamp_04227`。零值保持为零，阈值 155 保持原值，输入 156 时返回 155。
本规则用于固定输入分布和校验命中范围。查看原件段落可核对条件，定位到代码定义可确认上界和返回值。

[同原件下一用例](../../../glossaries/perf-10k/retry/perf-card-04228.md)
