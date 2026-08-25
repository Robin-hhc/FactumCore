# WiFiDemo code-only Agent 验收用例包

日期：2026-08-25

本目录只定义用例和判分依据，不包含 Agent、模型客户端、代码工具适配器、运行器或报告器。实验由外部 DeepSeek harness 执行。

## 文件

- `cases.yaml`：40 个公开问题；`NL01–NL20` 是自然语言到代码，`CF01–CF20` 是代码到流程。
- `pilot-cases.txt`：正式实验前使用的 12 题小样本。
- `gold/*.yaml`：逐题原子事实、源码证据和禁止主张草案。
- `gold/schema-example.yaml`：gold 字段示例，不参与评分。

## 固定样本

- 代码仓：`E:/WiFiDemo/WiFiDemo`
- revision：`8102322afbe5f81ecf6a35601ac4731ed14feb2d`
- Target：`chip2-wifi-host`、`chip8-wifi-host`、`chip2-wifi-device`、`chip8-wifi-device`
- 当前阶段：code-only；不得向模型提供 `knowledge_graph_qa.md`、研究文档、gold、历史答案或其他生成式领域文档。

路径仅说明本地样本位置。harness 可以复制或挂载同一 revision，但必须保存实际仓库地址、commit 和内容校验值。

## 三个实验条件

| 条件 | 模型可用的代码访问能力 |
|---|---|
| C0 | 项目实际基线：`grep/rg`、列文件、读取源码 |
| C1 | CodeGraph 的公开代码索引/探索能力，同时允许读取源码 |
| C2 | Joern 的符号、调用、控制流、dataflow、slice 等完整能力，同时允许读取源码 |

三组必须使用同一 DeepSeek 模型版本、system prompt、回答格式、上下文上限、工具调用上限、超时和源码读取能力。不得在某组失败后偷偷调用另一组工具。

## 外部 harness 输入

每次运行向模型提供：

1. 单个 `cases.yaml` 问题；
2. 允许访问的 Target 和 Side；
3. 当前实验条件的工具；
4. 统一回答要求；
5. 固定资源预算。

不要把 `tags`、gold facts、forbidden claims 或证据锚点拼入模型 prompt；它们只用于抽样、评分和审计。

建议统一要求模型输出：

```json
{
  "answer": "面向工程师的流程解释",
  "claims": [
    {
      "text": "一条可独立判断真假的原子主张",
      "target": "chip8-wifi-host",
      "side": "host",
      "confidence": "certain|candidate|unknown",
      "evidence": [
        {"file": "host/...", "line_start": 1, "line_end": 2, "symbol": "symbol_name"}
      ]
    }
  ],
  "insufficient_evidence": []
}
```

允许 harness 使用自己的字段名，但必须能还原每条主张、Target、Side、置信度和源码位置。Host/Device 之间应表达为 Event/Message/注册分发表衔接，不得伪造跨二进制 `CALLS`；chip2/chip8 比较也不得伪造成跨 Target 调用边。

## Gold 状态与评分

当前 40 份 gold 都是源码首轮核对后的 `draft`：

- `facts` 是应覆盖的原子事实；
- `critical` 标记不可缺失或不可答错的事实；
- `evidence` 是判分与人工复核锚点；
- `forbidden_claims` 捕获会改变流程含义的典型错误；
- `candidate` 表示源码只支持可能关系，不能升级为必然关系。

正式评分前必须由第二名人工 reviewer 独立检查完整性、Target/Side、关系强度、证据行和禁止主张，解决分歧后再把 `review.status` 改为 `approved`。在此之前只能用于 harness 接入调试，不能发布模型排名。

结果至少分开报告：

1. 关键事实通过率与全部事实覆盖率；
2. forbidden claim 命中数、错误 Target/Side、无证据主张；
3. 最终问题通过率；
4. 工具调用数、读取源码量、Token、时延和失败类型。

不要压缩成单一总分。关键事实错误、跨 Target 污染和伪造跨侧调用是硬失败，不能被速度或 Token 优势抵消。

## Pilot 与正式运行

先对 `pilot-cases.txt` 的 12 题各运行 C0/C1/C2，检查：

- 三组工具权限确实隔离；
- 问题、源码和 gold 没有泄漏；
- 所有回答都能回到源码；
- 预算、错误、重试和原始工具轨迹都被保存；
- 评分器能区分等价表述、遗漏和错误因果。

Pilot 只用于校准 harness 与评分协议，不用于选型。冻结 harness、prompt、工具版本和预算后，再对 40 题进行多次随机化正式运行，并分别报告两种问题方向和各类标签。
