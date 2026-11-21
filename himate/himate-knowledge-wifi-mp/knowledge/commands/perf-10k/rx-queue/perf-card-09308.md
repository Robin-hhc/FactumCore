---
id: perf-card-09308
doc_ref:
- doc_id: perf-doc-0931
  line_start: 47
  line_end: 51
code_ref:
- code_id: perf-code-09308
  symbol: perf_clamp_09308
  line_start: 3
  line_end: 7
tags: [perf-10k, radio, rx-queue]
lifecycle: stable
---
# 接收队列阈值用例 09308

用例 case09308 记录 接收队列中无线队列计数的边界行为。

## 适用条件

合成请求进入归一化阶段。参数为无符号计数，所属测试组为 rx-queue。

## 行为与验证

实现函数为 `perf_clamp_09308`。零值保持为零，阈值 129 保持原值，输入 130 时返回 129。
本规则用于固定输入分布和校验命中范围。查看原件段落可核对条件，定位到代码定义可确认上界和返回值。

[同原件下一用例](../../../runbooks/perf-10k/rx-queue/perf-card-09309.md)
