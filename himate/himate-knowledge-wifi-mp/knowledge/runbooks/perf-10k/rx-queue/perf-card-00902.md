---
id: perf-card-00902
doc_ref:
- doc_id: perf-doc-0091
  line_start: 11
  line_end: 15
code_ref:
- code_id: perf-code-00902
  symbol: perf_clamp_00902
  line_start: 3
  line_end: 7
tags: [perf-10k, radio, rx-queue]
lifecycle: stable
---
# 接收队列阈值用例 00902

用例 case00902 记录 接收队列中无线队列计数的边界行为。

## 适用条件

合成请求进入归一化阶段。参数为无符号计数，所属测试组为 rx-queue。

## 行为与验证

实现函数为 `perf_clamp_00902`。零值保持为零，阈值 153 保持原值，输入 154 时返回 153。
本规则用于固定输入分布和校验命中范围。查看原件段落可核对条件，定位到代码定义可确认上界和返回值。

[同原件下一用例](../../../glossaries/perf-10k/rx-queue/perf-card-00903.md)
