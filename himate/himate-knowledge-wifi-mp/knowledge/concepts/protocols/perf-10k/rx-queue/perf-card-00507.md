---
id: perf-card-00507
doc_ref:
- doc_id: perf-doc-0051
  line_start: 41
  line_end: 45
code_ref:
- code_id: perf-code-00507
  symbol: perf_clamp_00507
  line_start: 3
  line_end: 7
tags: [perf-10k, radio, rx-queue]
lifecycle: stable
---
# 接收队列阈值用例 00507

用例 case00507 记录 接收队列中无线队列计数的边界行为。

## 适用条件

合成请求进入归一化阶段。参数为无符号计数，所属测试组为 rx-queue。

## 行为与验证

实现函数为 `perf_clamp_00507`。零值保持为零，阈值 161 保持原值，输入 162 时返回 161。
本规则用于固定输入分布和校验命中范围。查看原件段落可核对条件，定位到代码定义可确认上界和返回值。

[同原件下一用例](../../../../rules/perf-10k/rx-queue/perf-card-00508.md)
