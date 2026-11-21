---
id: perf-card-03276
doc_ref:
- doc_id: perf-doc-0328
  line_start: 35
  line_end: 39
code_ref:
- code_id: perf-code-03276
  symbol: perf_clamp_03276
  line_start: 3
  line_end: 7
tags: [perf-10k, radio, link]
lifecycle: stable
---
# 链路状态阈值用例 03276

用例 case03276 记录 链路状态中无线队列计数的边界行为。

## 适用条件

合成请求进入归一化阶段。参数为无符号计数，所属测试组为 link。

## 行为与验证

实现函数为 `perf_clamp_03276`。零值保持为零，阈值 173 保持原值，输入 174 时返回 173。
本规则用于固定输入分布和校验命中范围。查看原件段落可核对条件，定位到代码定义可确认上界和返回值。

[同原件下一用例](../../../concepts/entities/perf-10k/link/perf-card-03277.md)
