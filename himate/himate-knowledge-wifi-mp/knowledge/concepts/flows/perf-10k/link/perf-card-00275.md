---
id: perf-card-00275
doc_ref:
- doc_id: perf-doc-0028
  line_start: 29
  line_end: 33
code_ref:
- code_id: perf-code-00275
  symbol: perf_clamp_00275
  line_start: 3
  line_end: 7
tags: [perf-10k, radio, link]
lifecycle: stable
---
# 链路状态阈值用例 00275

用例 case00275 记录 链路状态中无线队列计数的边界行为。

## 适用条件

合成请求进入归一化阶段。参数为无符号计数，所属测试组为 link。

## 行为与验证

实现函数为 `perf_clamp_00275`。零值保持为零，阈值 201 保持原值，输入 202 时返回 201。
本规则用于固定输入分布和校验命中范围。查看原件段落可核对条件，定位到代码定义可确认上界和返回值。

[同原件下一用例](../../../protocols/perf-10k/link/perf-card-00276.md)
