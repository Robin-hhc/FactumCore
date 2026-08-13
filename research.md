# 面向工业级嵌入式代码 Agent 的领域知识与代码事实架构调研

**日期：2026-08-12**  
**调研范围：重点关注 2026-02-12 ～ 2026-08-12 的论文、官方技术资料和近期项目数据**

## 摘要

本调研关注的问题不是“是否应该建设知识图谱”，而是：

> 面对百万级、宏密集、多 Target、Host/Device 分离的嵌入式 WiFi MAC 代码仓，Agent 应如何同时获得可靠的代码事实和工程领域知识？

近期研究和一线 Agent 厂商的实践表现出比较一致的趋势：

**代码结构索引负责提供可验证的程序事实；领域知识、工程经验和长期记忆独立管理；Agent 根据当前任务按需获取两类信息。**

建议的整体形态为：

```text
                    Agent / Workflow
                           |
                      WiFiGraph MCP
                           |
             +-------------+-------------+
             |                           |
    Engineering Knowledge          Code Fact Plane
             |                           |
   Metadata / Wiki / Skill              Joern CPG
             |                           |
 Feature / Flow / Event /        AST / Call / CFG /
 Target / Chip / Side /          Dataflow / Source
 Domain Rules / Edge Cases
```

这里所谓“分开”，主要指**事实来源、可信度、生命周期和更新方式分开**，并不强制要求物理上使用两个数据库。

---

# 第一部分：为什么领域知识与代码事实应该分层

## 1. Code Graph 能显著降低 Agent 的代码探索成本，但不能完全替代源码分析

2026 年论文 **Codebase-Memory: Tree-Sitter-Based Knowledge Graphs for LLM Code Exploration via MCP** 在 31 个真实代码仓、66 种语言上评估了持久化 Code Graph。

论文报告：

```text
Code Graph answer quality   ≈ 83%
File exploration            ≈ 92%

Token 使用                 ≈ 少 10 倍
Tool calls                  ≈ 少 2.1 倍
```

也就是说，结构化 Code Graph 最大的价值是：

> **让 Agent 用更低的 Context 和 Tool Call 成本定位结构事实，而不是完全替代源码探索。**

论文：  
https://arxiv.org/abs/2603.27277

开源实现：  
https://github.com/DeusData/codebase-memory-mcp citeturn911723search0turn911723search26


---

## 2. 工业领域知识确实能够显著提高 Coding Agent 的问题解决率

2026 年 4 月的 **SWE-Bench 5G** 与 WiFi MAC 场景尤其接近。

该研究从：

```text
free5GC
Open5GS
Magma
```

三个真实 5G Core 项目中构建了 210 个工程问题。

四个测试模型对 Bug 的诊断率都超过 **91%**，但最终 Resolve Rate 仍只有 **10%～30%**。

这说明：

> Agent 能找到相关代码，不代表 Agent 已经理解工程约束并能正确修改代码。

论文进一步对涉及 3GPP 规范的问题进行了领域知识注入实验。对于领域相关 Bug，加入对应 3GPP Specification Context 后：

```text
Policy authorization   +16.7 个百分点
Policy control         +25.0 个百分点
Session management     +20.0 个百分点
```

而普通 defensive check / nil-check 类问题基本没有收益。

论文：  
https://arxiv.org/abs/2604.26278

HTML全文：  
https://arxiv.org/html/2604.26278v1 citeturn911723search1turn911723search6


这对 WiFi MAC 有非常直接的映射：

```text
3GPP Domain Knowledge
        ↓
5G Core Agent
```

对应：

```text
Feature / Chip / Event / Protocol /
Host-Device / Known Edge Cases
        ↓
WiFi MAC Agent
```

因此，仅靠函数调用图、引用图或 CPG 仍不足以覆盖完整工程语义。

---

## 3. 但领域知识并不是“越多越好”

2026 年的 **SWE-Skills-Bench** 对 49 个公开 Agent Skill、约 565 个真实软件工程任务进行了带 Skill / 不带 Skill 的成对测试。

结果：

```text
49 个 Skill 中
39 个没有提高 pass rate

平均提升：
+1.2%

部分 Skill：
Token 增长最高 +451%
但 pass rate 不变

7 个高度匹配 Skill：
最高约 +30%

3 个不匹配 Skill：
最低约 -10%
```

论文：  
https://arxiv.org/abs/2603.15401

HTML全文：  
https://arxiv.org/html/2603.15401v1 citeturn911723search2turn911723search7


因此我们不应该建立：

```text
WiFi Everything Skill
        ↓
每次完整加载
```

而应该：

```text
当前函数
   ↓
识别 Feature / Flow / Target
   ↓
只获取当前任务相关知识
```

---

## 4. Google 的最新 Agent 架构也采用按需知识加载

Google 在 2026 年 4 月发布的 ADK Agent Skills 指南中，将领域知识加载明确拆成三级：

```text
L1 Metadata
约 100 tokens / skill

L2 Instructions
< 5000 tokens

L3 References
需要时才加载
```

Google 给出的示例中，如果存在 10 个 Skill：

```text
传统全部加载：
约 10,000 tokens

Progressive Disclosure：
启动时约 1,000 tokens
```

基础 Context 减少约 **90%**。

Google 官方文章：  
https://developers.googleblog.com/en/developers-guide-to-building-adk-agents-with-skills/ citeturn763227search2


这非常适合 WiFiGraph：

```text
L1
Function:
  flow = DATA_TX
  feature = TX_OFFLOAD
  side = HOST

        ↓ Agent认为需要进一步了解

L2
TX_OFFLOAD领域规则

        ↓ 需要证据

L3
设计资料 / Event定义 / Joern / 源码
```

---

## 5. GitHub Copilot 同样把 Repository Knowledge 与代码事实分开

GitHub 在 2026 年 3 月公开的 **Copilot Memory** 中，会保存 repository-specific knowledge，例如：

- coding conventions；
- architectural patterns；
- critical cross-file dependencies。

但是 GitHub 没有把这些 Memory 当作永久代码事实。

Memory：

- 使用前会和当前代码重新验证；
- repository scoped；
- 默认 28 天后过期。

GitHub 官方资料：  
https://github.blog/changelog/2026-03-04-copilot-memory-now-on-by-default-for-pro-and-pro-users-in-public-preview/ citeturn763227search1


这说明一个重要的工程原则：

> **长期知识、经验和代码事实应该拥有不同的生命周期。**

对于 WiFiGraph 同样应该：

```text
Joern CPG
→ 当前 Target 的代码事实

Engineering Knowledge
→ 可以长期存在，但允许失效、修正和重新验证
```

---

## 6. AWS 也把领域知识拆成 Skill、Reference 和 MCP

AWS 在 2026 年 2 月发布 Agent Plugins 时，明确将 Agent 专业能力拆为：

```text
Agent Plugin
├── Skills
├── MCP Servers
├── Hooks
└── References
```

其中：

- Skill：工作方式和专业 Workflow；
- Reference：领域资料、配置和知识；
- MCP：实时数据和工具；
- Hook：约束和自动化。

AWS 官方文章：  
https://aws.amazon.com/blogs/developer/introducing-agent-plugins-for-aws/ citeturn763227search0


AWS 明确提出这种设计可以避免反复把大量领域说明塞进 Prompt。

这与我们的目标非常接近：

```text
WiFi Skill / Workflow
        +
Engineering Knowledge
        +
WiFiGraph MCP
        +
Joern
```

---

## 7. “让 LLM 从源码自动生成一个权威知识库”风险较大

项目组对“没有文档、完全依赖 AI 生成知识图谱”的质疑是有依据的。

2026 年论文 **WiCER: Wiki-memory Compile, Evaluate, Refine** 对 17 个领域、6,800 个问题研究了把原始知识自动压缩成 Wiki 的效果。

直接进行 blind compilation：

```text
原始 Full Context      约 3.46

自动编译 Wiki：
2.14 ～ 2.32
```

并出现：

```text
53% ～ 60%
catastrophic failure
```

论文：  
https://arxiv.org/abs/2605.07068 citeturn538594academia30


通过诊断问题、发现遗漏事实、重新编译后，1～2 次迭代能够恢复约 80% 的质量损失。

因此 WiFiGraph 不应该：

```text
Source Code
    ↓
LLM
    ↓
“这个函数属于TX流程”
    ↓
直接成为权威事实
```

而应该保存 Provenance：

```text
build_verified
source_verified
manual
inferred
```

例如：

```text
chip8-host 中函数存在
→ build_verified

#ifdef FEATURE_MLO
→ source_verified

属于 DATA_TX
→ inferred

工程师确认属于 TX_COMPLETE
→ manual
```

---

## 8. 第一部分结论

近期论文和 Google、GitHub、AWS 的实践比较一致地支持：

### Code Fact Plane

负责：

```text
Function
Call
AST
CFG
Dataflow
Source Position
Target-specific Code
```

要求：

> 尽量确定、可追溯、机器验证。

---

### Engineering Knowledge Plane

负责：

```text
Feature
Flow
Target
Chip
Host / Device
Event
Protocol
Design Rationale
Known Edge Cases
```

要求：

> 允许自动推断和人工知识，但必须记录来源和可信度。

---

### Agent / Workflow

负责：

```text
当前应该查哪个Target？
应该读取哪个领域知识？
是否需要切换Host/Device？
需要检查哪些Edge Case？
这些代码事实最终意味着什么？
```

因此推荐：

> **领域知识与 Code Graph 在语义和可信度上分层，通过稳定实体进行关联，而不是建立一张所有 Edge 都被认为同样可靠的大知识图。**

---

# 第二部分：主流解决方案评估

## 9. Understand Anything

项目：  
https://github.com/Egonex-AI/Understand-Anything

中文说明：  
https://github.com/Egonex-AI/Understand-Anything/blob/main/READMEs/README.zh-CN.md

它是本次调研中比较接近：

> **Code Structure + Domain Semantics**

的项目。

其官方架构明确采用：

```text
Tree-sitter
→ deterministic structure

LLM
→ semantic understanding
```

Tree-sitter负责：

- import；
- function；
- class；
- call site；
- inheritance。

LLM负责：

- summary；
- tags；
- architecture layer；
- business domain mapping；
- guided tour。 citeturn566429search3turn566429search13


### 适合我们的部分

很适合借鉴：

```text
Function
→ Feature
→ Flow
→ Domain
```

这样的自动初始分类。

例如：

```text
hmac_tx_complete
        ↓
TX
DATA_TX
TX_COMPLETE
```

### 不适合直接替代 Joern 的原因

它的代码事实层主要来自 Tree-sitter。

对于普通软件工程：

```text
function
import
call
class
```

非常合适。

但是我们更关心：

```text
Target preprocessing
大量条件宏
CFG
Dataflow
复杂 function pointer
```

Understand Anything 的目标并不是 compiler-grade program analysis。

### 结论

```text
Engineering Knowledge：★★★★☆
Code Fact Depth：       ★★☆☆☆
WiFi直接使用：          不建议
值得借鉴：              非常高
```

适合用作 **Flow / Feature / Domain 自动分类 PoC**。

---

# 10. CodeGraph

项目：  
https://github.com/colbymchenry/codegraph

CodeGraph 主要属于：

> **高速 Code Intelligence / Structural Code Graph**

而不是领域知识系统。

---

### 性能

官方 7-repository benchmark 报告：

```text
Tool Calls   -88%
时间         -53%
Tokens       -62%
Cost         -44%
```

官方 benchmark：  
https://github.com/colbymchenry/codegraph/blob/main/README.md citeturn566429search1


这些属于**项目第一方数据**。

---

### 第三方测试

2026 年 6 月 HarrisonSec 对 Hono 进行了：

```text
40 runs
5 questions
Claude Opus 4.8
```

独立 A/B Test。

结果：

```text
Tool Calls
14.0 → 6.3
约 -55%

Latency
约 -20%

Cost
约 +6.8%
```

对于大范围 multi-file 问题：

```text
Tool Calls   -80%
Latency      -53%
Cost         -29%
```

第三方完整测试及原始 CSV：  
https://harrisonsec.com/blog/i-tested-codegraph-on-hono-benchmark/ citeturn566429search0


所以可以比较有把握地说：

> CodeGraph 的“减少 Agent 代码探索步骤”效果是有第三方数据支持的，但是否减少 Token/Cost 与代码仓大小和问题类型有关。

---

### 对 WiFi 最大的问题

CodeGraph 是 Tree-sitter 驱动的 structural graph。

对于我们的核心场景：

```text
C/C++
大量 #if / #ifdef
不同Target
generated config
复杂宏
```

需要额外验证 preprocessing correctness。

因此它非常适合：

```text
全仓快速导航
```

但目前不适合在未经验证的情况下直接承担：

```text
Target-specific source of truth
```

### 结论

```text
Engineering Knowledge：★☆☆☆☆
Code Navigation：       ★★★★★
Deep Program Analysis： ★★～★★★
WiFi直接替代Joern：     暂不建议
```

未来可能形成：

```text
CodeGraph
→ 快速Discovery

Joern
→ Target级深度验证
```

但 V1 没必要同时维护两个图。

---

# 11. Graphify

项目：  
https://github.com/Graphify-Labs/graphify

Benchmark：  
https://github.com/Graphify-Labs/graphify/blob/v8/BENCHMARKS.md

Graphify 的定位更偏：

> **Code + Docs + Memory Knowledge Graph**

其 benchmark 同时覆盖：

```text
Long-term memory
+
Code intelligence
```

在约 1M LOC 的 ERPNext 代码仓测试中：

```text
grep/read Agent
key-fact coverage = 70.8%

增加 Graphify Tool
= 82.0%
``` citeturn566429search2turn566429search5


Graphify 的 Memory Benchmark 还报告：

```text
LOCOMO n=300
Recall@10 = 0.497
QA = 45.3%

LongMemEval-S n=50
QA = 76%
```

需要注意：

> 这些目前仍主要属于项目第一方 benchmark，而不是独立论文复现。

### 最大参考价值

Graphify 非常值得我们借鉴的是：

> **知识 Edge 必须带 provenance / confidence。**

这非常符合：

```text
source_verified
build_verified
manual
inferred
```

的 WiFiGraph 模型。

### 结论

```text
Engineering Knowledge：★★★★☆
Code Fact：             ★★★☆☆
领域知识设计参考：      非常高
替代Joern：             不建议
```

---

# 12. GitNexus

项目：  
https://github.com/abhigyanpatwari/GitNexus

GitNexus 当前已经提供：

```text
call graph
impact
execution process
multi-repo
MCP
```

并持续增强 C/C++ resolution。

但是 GitNexus 自己也在公开追踪完整 ISO C++ semantic resolution 的差距。

C++ Conformance Issue：  
https://github.com/abhigyanpatwari/GitNexus/issues/1890 citeturn538594search0turn538594search3


近期 C++ indexing 还出现过 linking-symbols 性能/稳定性问题：

https://github.com/abhigyanpatwari/GitNexus/issues/1973

https://github.com/abhigyanpatwari/GitNexus/issues/2243 citeturn538594search6turn538594search9


### 判断

GitNexus 比简单 Tree-sitter Code Graph 更接近完整 Code Intelligence。

因此它值得进入我们自己的：

```text
WiFiDemo Benchmark
```

但考虑：

```text
大量宏
Target preprocessing
函数钩子
复杂C/C++
```

目前仍不建议未经验证直接代替 Joern。

---

# 13. LLM-Wiki

论文：

https://arxiv.org/abs/2605.25480

**Retrieval as Reasoning: Self-Evolving Agent-Native Retrieval via LLM-Wiki**

LLM-Wiki 不属于 Code Graph。

它属于：

> **Narrative / Domain Knowledge Retrieval**

它把资料编译为：

```text
Wiki Page
+
Bidirectional Links
+
Search
+
Read
+
Follow Link
+
Error Book
```

在：

```text
HotpotQA
MuSiQue
2WikiMultiHopQA
```

上，相比最强 Graph-based baseline 提高：

```text
约 2.0 ～ 8.1 F1
``` citeturn538594academia27


---

### 对 WiFi 的意义

非常适合：

```text
MLO设计说明
TX recovery特殊情况
芯片历史workaround
Event协议说明
设计原因
Known Edge Cases
```

因为这些信息很难可靠表达为：

```text
CALLS
DEPENDS_ON
```

这样的程序图关系。

---

### 但是 Wiki 不能替代原始知识

前面提到的 WiCER 已经证明 blind compilation 存在非常明显的信息丢失：

https://arxiv.org/abs/2605.07068

因此：

```text
Raw Knowledge
      +
Compiled Wiki
```

应该同时保留。

另一项 2026 年的 preregistered RAG vs Wiki 实验也发现：

- Wiki 更擅长跨文档 synthesis；
- RAG 更适合单事实检索；
- Wiki 查询 Token 成本不一定更低。

论文：

https://arxiv.org/abs/2605.18490 citeturn763227academia57


### 结论

```text
Engineering Knowledge：★★★★★
Code Facts：            ☆☆☆☆☆
Edge Case / Design知识：非常适合
替代Joern：             完全不是同类产品
```

---

# 14. Joern

官网：  
https://joern.io/

官方文档：  
https://docs.joern.io/

GitHub：  
https://github.com/joernio/joern

Joern 的定位非常明确：

> Code Property Graph / Program Analysis。

它能够表达：

```text
AST
CFG
Call
Control Dependence
Data Dependence
Dataflow
```

官方当前对 C/C++ frontend 的 maturity 标记为：

```text
Very High
``` citeturn538594search2turn538594search8


---

## Joern 与 Agent 的结合已经有近期研究实现

2026 年论文：

**Bridging Code Property Graphs and Language Models for Program Analysis**

论文：  
https://arxiv.org/abs/2603.24837

开源 codebadger：  
https://github.com/lekssays/codebadger citeturn538594search1turn538594search10


codebadger 直接采用：

```text
Joern CPG
    ↓
High-level MCP
    ↓
Agent
```

Agent不需要自己写复杂 CPGQL。

它直接提供：

```text
program slicing
taint tracking
dataflow
semantic navigation
```

论文展示的案例包括：

- 在约 8,000-method 代码仓中导航；
- 发现此前未报告的 libtiff buffer overflow；
- 对 CVE-2025-6021 首次生成正确 patch。 citeturn538594search1turn538594search7


因此我们完全可以借鉴：

> **Joern 不直接暴露给 Agent，而是包装为有限、稳定的 MCP 工具。**

---

# 15. 横向定位

| 方案 | Code Facts | Domain Knowledge | 深度程序分析 | 更适合 WiFiGraph 哪层 |
|---|---:|---:|---:|---|
| Understand Anything | ★★★ | ★★★★ | ★★ | Metadata 自动分类 |
| CodeGraph | ★★★★ | ★ | ★★ | 快速 Code Navigation |
| Graphify | ★★★ | ★★★★ | ★★ | Engineering Knowledge |
| GitNexus | ★★★★ | ★★ | ★★★ | Code Navigation / PoC候选 |
| LLM-Wiki | ☆ | ★★★★★ | ☆ | Domain Wiki / Edge Cases |
| Joern | ★★★★★ | ☆ | ★★★★★ | Target Code Fact |

---

# 16. 为什么目前仍建议 Joern，而不是直接采用 CodeGraph

这次调研以后，这个论点应该说得更加准确：

> **不是因为 CodeGraph 不成熟。**

实际上 CodeGraph 在：

```text
索引速度
增量更新
Agent Tool Call
大仓导航
```

方面非常有吸引力，而且有第三方 A/B 数据支持：

https://harrisonsec.com/blog/i-tested-codegraph-on-hono-benchmark/ citeturn566429search0


真正的问题是我们的核心风险属于：

```text
Macro-heavy C/C++
+
Target-specific preprocessing
+
公共代码
+
ops / hook
+
复杂控制流
+
后续 dataflow
```

而我们的首要要求应该是：

```text
1. 不把 Agent 导错
2. 然后才是减少 Tool Call
```

Joern 当前在：

```text
CFG
PDG
Dataflow
Taint
Program Slicing
```

上的能力边界更明确，并且已经存在近期 Joern→MCP 的公开研究实现：

https://arxiv.org/abs/2603.24837

因此现阶段更适合作为：

> **WiFi Target 内部的深度 Code Fact Engine。**

---

## 17. 但这个结论仍然需要我们自己验证

目前没有找到一份近期独立论文直接进行：

```text
Joern
vs
CodeGraph
vs
GitNexus
```

在：

```text
macro-heavy embedded C/C++
```

上的准确率 head-to-head benchmark。

因此不应该声称：

> Joern 已经被公开研究证明一定更适合 WiFi。

正确表述应该是：

> **根据当前公开能力边界，Joern 与我们的风险模型更匹配；最终选择应通过真实 WiFi MAC Benchmark 验证。**

---

# 18. 推荐 WiFiGraph 最终分层

综合论文和项目实践，建议最终形成三类知识资产：

```text
                  WiFiGraph MCP

        +-------------+-------------+
        |             |             |
   Code Facts     Metadata      Domain Knowledge
        |             |             |
      Joern         SQLite       Wiki / Skill
        |             |             |
 AST / CFG        Target         Design Rules
 Dataflow         Chip           Edge Cases
 Call             Side           Known Issues
 Source           Feature        Protocol
                  Flow
                  Event
```

---

## Code Facts

来源：

```text
Joern
Build
Source
```

可信度：

```text
verified
```

---

## Structured Engineering Metadata

例如：

```text
Function ↔ Target
Function ↔ Feature
Function ↔ Flow
Function ↔ Event
Target ↔ Macro
Target ↔ Side
```

来源可以是：

```text
source
build
rule
manual
inferred
```

必须保留 provenance。

---

## Narrative Engineering Knowledge

例如：

```text
为什么这么设计
Feature之间的耦合
协议约束
Known Edge Cases
历史Workaround
调试经验
```

适合：

```text
Wiki
Reference
Skill
```

而不是硬编码成 Code Graph。

---

# 19. 对项目组争议的最终回答

我们不应该提出：

> “建设一个 AI 自动生成的 WiFi 知识图谱，并认为它能够理解整个驱动。”

这个方案确实风险很高。

更合理的工程目标是：

> **采用成熟 Program Analysis 作为代码事实层，同时建设一个小而可维护的 Engineering Knowledge Layer，把代码中无法表达的 Target、Feature、Flow、Event、芯片和领域经验提供给 Agent。**

近期研究支持：

```text
Code Graph
→ 大幅降低代码探索成本
```

参考：  
https://arxiv.org/abs/2603.27277

领域 Benchmark 支持：

```text
Domain Knowledge
→ 在真正领域相关问题上显著提高解决率
```

参考：  
https://arxiv.org/abs/2604.26278

Skill Benchmark 又证明：

```text
Knowledge 必须按需匹配
而不是全部注入
```

参考：  
https://arxiv.org/abs/2603.15401

Google / GitHub / AWS 的最新产品架构也都在采用：

```text
Persistent Knowledge
+
On-demand Context
+
Tools / MCP
+
Agent Reasoning
```

参考：

Google：  
https://developers.googleblog.com/en/developers-guide-to-building-adk-agents-with-skills/

GitHub：  
https://github.blog/changelog/2026-03-04-copilot-memory-now-on-by-default-for-pro-and-pro-users-in-public-preview/

AWS：  
https://aws.amazon.com/blogs/developer/introducing-agent-plugins-for-aws/

因此 WiFiGraph 最合理的目标不是发明一种新的“大知识图谱”，而是：

> **把工业 WiFi MAC 特有的 Engineering Knowledge 与成熟的 Code Intelligence 串联起来，为 Agent 提供按需、可验证、可追溯的工程上下文。**

---

# 20. 建议下一步：建立 WiFi MAC Benchmark

最终技术选型不能只依赖公开项目 benchmark。

建议使用真实 WiFiDemo / WiFi MAC Target 构造约 30～50 个 ground-truth case：

```text
direct call
跨文件调用

#if / #ifdef
Target存在性

公共代码
芯片差异

ops hook
function pointer

Host Event Producer
Device Event Consumer

CFG
简单Dataflow
```

对比：

```text
Joern
CodeGraph
GitNexus
```

指标：

```text
Call Precision / Recall

Target correctness

Macro-conditioned
occurrence correctness

Hook correctness

Index Time
Incremental Time

Query Latency

Agent Tool Calls
Agent Tokens

最终任务正确率
```

只有完成这一步以后，才能真正回答：

> **Joern 是否应该成为 WiFiGraph 最终 Code Fact Engine。**

公开资料可以帮助我们缩小候选范围，但最终工程证据应该来自我们自己的 WiFi MAC 代码形态。
