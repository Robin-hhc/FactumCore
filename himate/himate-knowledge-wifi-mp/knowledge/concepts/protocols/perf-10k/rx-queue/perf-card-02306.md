---
id: perf-card-02306
doc_ref:
- doc_id: perf-doc-0231
  line_start: 35
  line_end: 39
code_ref:
- code_id: perf-code-02306
  symbol: perf_clamp_02306
  line_start: 3
  line_end: 7
tags: [perf-10k, radio, rx-queue]
lifecycle: stable
---
# 接收队列阈值用例 02306

用例 case02306 记录 接收队列中无线队列计数的边界行为。

## 适用条件

合成请求进入归一化阶段。参数为无符号计数，所属测试组为 rx-queue。

## 行为与验证

实现函数为 `perf_clamp_02306`。零值保持为零，阈值 117 保持原值，输入 118 时返回 117。
本规则用于固定输入分布和校验命中范围。查看原件段落可核对条件，定位到代码定义可确认上界和返回值。

[同原件下一用例](../../../../rules/perf-10k/rx-queue/perf-card-02307.md)
