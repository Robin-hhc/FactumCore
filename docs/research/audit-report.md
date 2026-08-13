# 架构研究最终审计报告

审计日期：2026-08-14

## 1. 结论

本轮审计通过。`research.md` 的核心结论只使用论文/公开 Benchmark、AI 公司技术文章、开源项目官方材料和标准；没有搜索结果页或二手媒体进入正文。当前研究没有声称执行过 WiFiDemo 候选工具实验，没有确定唯一方案，也没有用 aggregate score 覆盖 Target、源码证据或不确定性硬门槛。

审计中发现 RepoMem 的 OpenReview PDF 会进入 browser challenge、Fraunhofer CPG 旧文档主页会重定向；正文已分别改为可直接访问的 arXiv 原文和官方 GitHub 仓库。随后重新打开并核验。

## 2. 证据规模

| 项目 | 数量 | 口径 |
|---|---:|---|
| 登记来源 | 36 | `S001–S036` |
| claim-verified | 12 | 已复核原始论文/结果中的可引用声明 |
| primary-read | 24 | 官方论文/文档/仓库/标准已阅读，但不声称 WiFiDemo 复现 |
| 论文/公开 Benchmark | 12 | 互斥主分类；含经典 CPG 论文和开源伴随论文 |
| AI 公司技术文章 | 2 | Google/AWS Skills 与 GitHub Copilot Memory；Microsoft RepoMem 按论文计 |
| 开源项目官方材料 | 21 | 项目文档、README、release 与构建文档 |
| 标准 | 1 | SWHID/PROV-O/SARIF 合并登记为一个标准来源组 |
| 正文含量化结果的行 | 7 | 每行均含直接原始 URL、来源身份和外推限制 |

分类数字使用互斥主分类，避免同一“论文 + 公司页面”重复计数。来源状态只有 `claim-verified` 和 `primary-read`；无 rejected source 进入结论。

## 3. 候选与实验规模

| 项目 | 数量 | 说明 |
|---|---:|---|
| 固定维度方案 profile | 24 | R01–R07、A01–A10、H01–H07 |
| 排除为完整方案的对象组 | 5 | 能力仍可作为组件/参考，不表示项目毫无价值 |
| 架构参考组 | 4 | identity、混合图、memory/Wiki、声明式查询 |
| 组件候选组 | 5 | compiler/identity、CPG、deep analysis、navigation、rule/knowledge delivery |
| 完整架构短名单 | 3 | L1 compiler-native、L2 Target-specific CPG、L3 discovery + verification |
| Benchmark backlog | 15 | B01–B10 WiFiDemo 主线，B11–B15 跨仓/知识/运维/许可 |
| 外部 C 案例仓 | 3 | Zephyr、RIOT、Contiki-NG；均固定 tag/hash 与许可证边界 |

上述“排除/参考/组件”以证据矩阵中的对象组为计数单位，不与 24 个 profile 强行一一对应。短名单是架构族，不是已经胜出的产品组合。

## 4. 审计项目

### 4.1 数字与来源

运行：

```powershell
rg -n '[0-9]+([.,][0-9]+)?%|[0-9]+([.,][0-9]+)?[×xX]|[0-9]+ 个|[0-9]+ 倍' research.md
```

结果为 7 行，全部位于“数字证据的解释规则”表；每行有论文、公司原文或项目第一方 Benchmark 的直接 URL，并显式说明不能外推到 WiFiDemo 的内容。

### 4.2 正文 URL

从 Markdown 正文提取 37 个唯一 HTTP(S) URL，逐一打开。最终正文 URL 全部落到论文原文、AI 公司文章、开源项目官方文档/仓库/release 或标准正文。没有搜索页、聚合博客或不可读 challenge 页保留在正文。

### 4.3 来源 ID 与本地链接

- 正文和 `docs/research` 中没有 undefined `Sxxx`；
- `S001–S036` 均在 ledger 外的研究材料中至少被引用一次；
- `research.md` 链接的六个研究附录均存在；
- WiFiDemo 案例明确指向 W01–W08，未伪装成工具实测。

### 4.4 代码—领域链接

以下概念在正文和专门调研中均有明确语义：Source Entity、Target Occurrence、typed Assertion、repository/revision/Target、file:line、generator/provenance、confidence/review、conflict、stale/invalid、双向导航和重新验证。Host/Device Event 使用协议实体连接两个编译视角，不伪装为直接 C 调用。

### 4.5 范围与措辞

范围词审计只命中“当前证据不足以确定唯一方案”等否定/限制语句。正文没有“已经证明某方案适用于 WiFi”“一定优于”“直接替代”或“必须采用某产品”的结论。开源偏好只作为无决定性差异时的 tie-break。

### 4.6 格式与占位

占位标记扫描与 `git diff --check` 均无错误。审计命令本身不写入正文，以免被后续占位扫描误判为待办内容。

## 5. 仍然开放的问题

审计通过不等于架构选型完成。多 Target compdb、宏分支、函数指针、Event 链接、稳定 ID、失效修复、Agent 最终效果、资源和许可证组合仍需按 `benchmark-backlog.md` 实验。任何新的量化结论必须追加 fixed version、原始输出和 counterfactual；不能把本报告的文献审计状态升级为工程验证状态。
