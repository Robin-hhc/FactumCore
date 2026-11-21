---
id: perf-card-01048
doc_ref:
- doc_id: perf-doc-0105
  line_start: 47
  line_end: 51
code_ref:
- code_id: perf-code-01048
  symbol: perf_clamp_01048
  line_start: 3
  line_end: 7
tags: [perf-10k, radio, session]
lifecycle: stable
---
# 会话配额阈值用例 01048

用例 case01048 记录 会话配额中无线队列计数的边界行为。

## 适用条件

合成请求进入归一化阶段。参数为无符号计数，所属测试组为 session。

## 行为与验证

实现函数为 `perf_clamp_01048`。零值保持为零，阈值 145 保持原值，输入 146 时返回 145。
本规则用于固定输入分布和校验命中范围。查看原件段落可核对条件，定位到代码定义可确认上界和返回值。

[同原件下一用例](../../../runbooks/perf-10k/session/perf-card-01049.md)
