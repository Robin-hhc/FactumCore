---
id: perf-card-08622
doc_ref:
- doc_id: perf-doc-0863
  line_start: 11
  line_end: 15
code_ref:
- code_id: perf-code-08622
  symbol: perf_clamp_08622
  line_start: 3
  line_end: 7
tags: [perf-10k, radio, retry]
lifecycle: stable
---
# 重试计数阈值用例 08622

用例 case08622 记录 重试计数中无线队列计数的边界行为。

## 适用条件

合成请求进入归一化阶段。参数为无符号计数，所属测试组为 retry。

## 行为与验证

实现函数为 `perf_clamp_08622`。零值保持为零，阈值 170 保持原值，输入 171 时返回 170。
本规则用于固定输入分布和校验命中范围。查看原件段落可核对条件，定位到代码定义可确认上界和返回值。

[同原件下一用例](../../../runbooks/perf-10k/retry/perf-card-08623.md)
