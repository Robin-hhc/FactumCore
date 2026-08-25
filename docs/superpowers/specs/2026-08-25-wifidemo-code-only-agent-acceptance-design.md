# WiFiDemo code-only Agent 验收用例设计

日期：2026-08-25

状态：用例包已设计；等待外部 DeepSeek harness 接入与第二人工 gold 评审。

冻结样本：`E:/WiFiDemo/WiFiDemo`，commit `8102322afbe5f81ecf6a35601ac4731ed14feb2d`。

## 1. 交付边界

本轮只设计验收题、事实依据、反事实和实验协议。本仓不实现 Agent、DeepSeek 客户端、C0/C1/C2 工具封装、运行编排、评分程序或结果报告程序；这些由用户的 DeepSeek harness 负责。

可直接接入的材料位于 [`benchmark/wifidemo/`](../../../benchmark/wifidemo/)：

- 40 题公开题库；
- 12 题 pilot 子集；
- 40 份 source-anchored gold 草案；
- 外部 harness 的输入、输出和隔离约束。

## 2. 研究问题

实验只回答代码索引能力能否支持两类真实问答：

1. **自然语言到代码**：从功能、状态、日志或协议说法定位当前 Target 下的文件、符号、调用/事件步骤和源码证据；
2. **代码到流程**：从函数、变量、字段、宏、ops 成员或事件枚举出发，解释上游来源、下游影响、分支条件、跨 Target 差异和 Host/Device 消息衔接。

对比三个条件：

| 条件 | 知识访问能力 | 要验证的假设 |
|---|---|---|
| C0 | `grep/rg`、列文件、读取源码 | 项目现有低成本方式是否已经足够 |
| C1 | CodeGraph 完整公开能力 + 源码读取 | 轻量结构图能否提高正确性或降低探索成本 |
| C2 | Joern 完整能力 + 源码读取 | CPG、控制流、dataflow、slice 是否改善复杂流程题 |

Joern 不拆成 shallow/deep 两组：真实使用时已有能力全部提供给模型。编译工件用于确认 Target 真值，不是第四个候选。

本阶段禁止领域文档，目的是检验对 WiFiDemo 这种较小、命名和注释较充分的项目，单靠代码是否足够。即使 code-only 通过，也不能外推为真实 WiFi MAC 大仓不需要文档；若失败，也不能直接推出加入文档必然解决问题。

## 3. 题库结构

题库共 40 题：

- `NL01–NL20`：自然语言到代码；
- `CF01–CF20`：代码到流程；
- P0 是会直接影响技术结论的核心题，P1 用于扩大行为覆盖；
- `allowed_targets` 和 `allowed_sides` 定义合法取证范围；
- `tags` 用于分层统计，不提供给模型。

覆盖内容包括：

- chip2/chip8 宏与运行时能力差异；
- Host/Device 内部调用、函数指针和注册表；
- TX、Ring、BA、VAP、User、Timer、HCC/FRW 事件；
- 控制条件、状态生命周期、数据去向与失败回滚；
- Host/Device 消息衔接和“不得伪造跨二进制调用”的负例；
- 源码意图与可执行接收路径不一致时的证据不足表达。

12 题 pilot 兼顾两个方向、Target 差异、函数指针、控制/dataflow、跨侧 Event 和已知反事实，详见 `pilot-cases.txt`。

## 4. 信息边界

所有条件共同允许：

- 固定 revision 的 `.c`、`.h`、CMake、构建脚本和编译工件；
- 源码原有注释、日志、命名和枚举；
- 统一的源码读取、文件列表和 Target 列表能力；
- 四个 Target 的独立视图。

所有条件共同禁止：

- `knowledge_graph_qa.md`；
- `docs/verification/analysis-tool-verification.md`；
- README、设计说明、研究论文、生成 Wiki、gold、历史答案与历史运行轨迹；
- 人工预置的 Feature、Flow、Step、Domain 或跨侧链接；
- 在 prompt 中提示应访问哪些文件、函数或事实。

C0 不得隐藏使用 C 解析器或调用图；C1 不得混入 Joern/CPG；C2 可使用 Joern 的完整公开分析能力。任何工具臂失败都应原样计为该组失败，不自动回退到另一组。

## 5. Target 与跨侧语义

实验的硬约束是：

- chip2/chip8 是不同 Target 视图，不能建立跨 Target `CALLS`；
- shared 源文件可以内容相同，但每个 Target 的 occurrence、生效宏和 active branch 必须独立判断；
- Host/Device 通过 Event、Message、枚举值、队列和注册/分发表衔接，不能建立跨二进制 `CALLS`；
- 对函数指针和异步路径，应区分 `candidate`、`may` 与源码可证明的 `must`；
- 没有足够代码证据时必须显式保留不确定性。

## 6. Gold 设计

每题 gold 由以下元素组成：

- 原子事实及稳定 ID；
- 事实是否关键；
- subject/relation/object；
- Target、Side、置信度和允许的等价说法；
- `file:line` 与 symbol 证据；
- 会改变结论的 forbidden claims。

Gold 不要求模型逐字匹配；评分应判断语义等价和证据是否支撑。禁止主张只记录实质错误，例如把 `mode` 误写成当前分流字段、把 Event 写成跨侧直接调用、把候选函数指针写成必然调用。

当前 gold 只完成首轮源码核对，全部保持 `draft`。正式运行前必须经过第二人工 reviewer 独立复核并改为 `approved`。

## 7. 判分维度

两类问题分别报告，不合并成一个总冠军分数。

### 7.1 自然语言到代码

- 关键文件、符号和证据锚点覆盖率；
- Target/Side 正确率；
- 完整流程步骤与 Event/Message 衔接；
- 无关候选、无依据主张和无答案时的拒答；
- 工具调用、源码读取量、Token 与时延。

### 7.2 代码到流程

- 原子事实和关键步骤覆盖率；
- 顺序、控制条件、数据去向与失败分支；
- 函数指针、跨 Target 和跨侧关系强度是否准确；
- 证据覆盖和 forbidden claim；
- 工具调用、源码读取量、Token 与时延。

关键事实错误、错误 Target、Target 泄漏或伪造跨二进制 `CALLS` 是硬失败，不能由成本优势抵消。

## 8. 外部 harness 控制

外部 harness 应固定：

- WiFiDemo revision 与四个 Target；
- DeepSeek 模型的精确版本/服务标识；
- system prompt、回答 schema、温度、推理开关；
- 上下文、输出 Token、工具调用和 wall-time 预算；
- C0/C1/C2 版本、索引配置和每组可见工具；
- 重试、超时、随机化、重复次数和失败记账方式。

每次运行保存问题、实验条件、Target、原始工具调用/返回、读取源码、最终答案、模型/工具版本、Token、时延与错误。评分时才读取 gold。

## 9. 执行顺序与结论边界

1. 用 12 题 pilot 验证隔离、输出格式、记录完整性和评分语义；不据此选型。
2. 冻结 harness、prompt、工具版本和预算。
3. 对 40 题进行多次随机化运行。
4. 分别报告 NL/CF、P0/P1、Target 差异、跨侧、控制/dataflow 和函数指针题。
5. 对接近的结果报告方差和失败样例，不仅报告均值。

允许得出的结论：

- C0 已满足 WiFiDemo；
- C1 在正确性或检索成本上相对 C0 有增量；
- C2 只在控制/dataflow/间接调用题上有增量，适合按需启用；
- C2 在普通题也稳定领先且成本可接受，支持作为默认代码事实层；
- 三者效果无可区分差异时，按开源、离线、适配与运维成本裁决。

在正式实验完成前，本用例包不支持宣布任何工具胜出，也不支持宣布 WiFiDemo 或真实项目不需要文档。
