---
id: perf-card-03733
doc_ref:
- doc_id: perf-doc-0374
  line_start: 17
  line_end: 21
code_ref:
- code_id: perf-code-03733
  symbol: perf_clamp_03733
  line_start: 3
  line_end: 7
tags: [perf-10k, radio, buffer]
lifecycle: stable
---
# 缓冲容量阈值用例 03733

用例 case03733 记录 缓冲容量中无线队列计数的边界行为。

## 适用条件

合成请求进入归一化阶段。参数为无符号计数，所属测试组为 buffer。

## 行为与验证

实现函数为 `perf_clamp_03733`。零值保持为零，阈值 223 保持原值，输入 224 时返回 223。
本规则用于固定输入分布和校验命中范围。查看原件段落可核对条件，定位到代码定义可确认上界和返回值。

[同原件下一用例](../../../protocols/perf-10k/buffer/perf-card-03734.md)
