---
id: perf-card-07445
doc_ref:
- doc_id: perf-doc-0745
  line_start: 29
  line_end: 33
code_ref:
- code_id: perf-code-07445
  symbol: perf_clamp_07445
  line_start: 3
  line_end: 7
tags: [perf-10k, radio, session]
lifecycle: stable
---
# 会话配额阈值用例 07445

用例 case07445 记录 会话配额中无线队列计数的边界行为。

## 适用条件

合成请求进入归一化阶段。参数为无符号计数，所属测试组为 session。

## 行为与验证

实现函数为 `perf_clamp_07445`。零值保持为零，阈值 81 保持原值，输入 82 时返回 81。
本规则用于固定输入分布和校验命中范围。查看原件段落可核对条件，定位到代码定义可确认上界和返回值。

[同原件下一用例](../../../commands/perf-10k/session/perf-card-07446.md)
