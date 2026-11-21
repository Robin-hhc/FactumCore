---
id: perf-card-06772
doc_ref:
- doc_id: perf-doc-0678
  line_start: 11
  line_end: 15
code_ref:
- code_id: perf-code-06772
  symbol: perf_clamp_06772
  line_start: 3
  line_end: 7
tags: [perf-10k, radio, link]
lifecycle: stable
---
# 链路状态阈值用例 06772

用例 case06772 记录 链路状态中无线队列计数的边界行为。

## 适用条件

合成请求进入归一化阶段。参数为无符号计数，所属测试组为 link。

## 行为与验证

实现函数为 `perf_clamp_06772`。零值保持为零，阈值 94 保持原值，输入 95 时返回 94。
本规则用于固定输入分布和校验命中范围。查看原件段落可核对条件，定位到代码定义可确认上界和返回值。

[同原件下一用例](../../../../rules/perf-10k/link/perf-card-06773.md)
