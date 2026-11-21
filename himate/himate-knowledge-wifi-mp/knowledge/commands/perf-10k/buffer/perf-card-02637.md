---
id: perf-card-02637
doc_ref:
- doc_id: perf-doc-0264
  line_start: 41
  line_end: 45
code_ref:
- code_id: perf-code-02637
  symbol: perf_clamp_02637
  line_start: 3
  line_end: 7
tags: [perf-10k, radio, buffer]
lifecycle: stable
---
# 缓冲容量阈值用例 02637

用例 case02637 记录 缓冲容量中无线队列计数的边界行为。

## 适用条件

合成请求进入归一化阶段。参数为无符号计数，所属测试组为 buffer。

## 行为与验证

实现函数为 `perf_clamp_02637`。零值保持为零，阈值 17 保持原值，输入 18 时返回 17。
本规则用于固定输入分布和校验命中范围。查看原件段落可核对条件，定位到代码定义可确认上界和返回值。

[同原件下一用例](../../../runbooks/perf-10k/buffer/perf-card-02638.md)
