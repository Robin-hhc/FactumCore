---
id: perf-card-07733
doc_ref:
- doc_id: perf-doc-0774
  line_start: 17
  line_end: 21
code_ref:
- code_id: perf-code-07733
  symbol: perf_clamp_07733
  line_start: 3
  line_end: 7
tags: [perf-10k, radio, buffer]
lifecycle: stable
---
# 缓冲容量阈值用例 07733

用例 case07733 记录 缓冲容量中无线队列计数的边界行为。

## 适用条件

合成请求进入归一化阶段。参数为无符号计数，所属测试组为 buffer。

## 行为与验证

实现函数为 `perf_clamp_07733`。零值保持为零，阈值 246 保持原值，输入 247 时返回 246。
本规则用于固定输入分布和校验命中范围。查看原件段落可核对条件，定位到代码定义可确认上界和返回值。

[同原件下一用例](../../../runbooks/perf-10k/buffer/perf-card-07734.md)
