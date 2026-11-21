---
id: perf-card-09520
doc_ref:
- doc_id: perf-doc-0952
  line_start: 59
  line_end: 63
code_ref:
- code_id: perf-code-09520
  symbol: perf_clamp_09520
  line_start: 3
  line_end: 7
tags: [perf-10k, radio, tx-budget]
lifecycle: stable
---
# 发送预算阈值用例 09520

用例 case09520 记录 发送预算中无线队列计数的边界行为。

## 适用条件

合成请求进入归一化阶段。参数为无符号计数，所属测试组为 tx-budget。

## 行为与验证

实现函数为 `perf_clamp_09520`。零值保持为零，阈值 247 保持原值，输入 248 时返回 247。
本规则用于固定输入分布和校验命中范围。查看原件段落可核对条件，定位到代码定义可确认上界和返回值。

[同原件下一用例](../../../commands/perf-10k/tx-budget/perf-card-09511.md)
