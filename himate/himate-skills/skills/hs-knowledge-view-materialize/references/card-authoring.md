# 卡头、引用与模板

按计划中的主题选本 Skill 的骨架，填写有依据的段落。标题写正文 H1。

| 主题 | 模板 |
|---|---|
| 对象与职责 | [对象](templates/entity.md) |
| 调用或操作链路 | [流程](templates/flow.md) |
| 协议格式与行为 | [协议](templates/protocol.md) |
| 约束或判断条件 | [规则](templates/rule.md) |
| 命令和用法 | [命令](templates/command.md) |
| 排障和验证步骤 | [操作手册](templates/runbook.md) |
| 术语及含义 | [术语](templates/glossary.md) |

新卡头的必填字段为 `id`、`doc_ref`、`code_ref`。沿用计划 ID，普通更新不分配新 ID。`doc_ref` 至少一项，每项填已登记的 `doc_id` 和真实定位。`code_ref` 覆盖计划中的 `required_code_refs`，纯文档卡可填 `[]`。每项填 `code_id`、`line_start`、`line_end`，函数可加已验证的 `symbol`，宏或结构体使用对应类型的 `selector`。可选字段 `tags` 是非空且不重复的字符串组成的数组，也可为空数组。数字和布尔形式的标签请加引号。`lifecycle` 可填 `stable` 或 `deprecated`，缺省按未退役处理，具体状态按 P2 决定。

## 源码定位

裸字符串 `symbol: start_rx` 是 `selector: {kind: function, name: start_rx}` 的函数定义简写，不是任意代码名字的通用字段。宏、枚举和 typedef 等按实际声明选择类型：

| 实际声明 | 引用定位示例 |
|---|---|
| `#define RX_LIMIT ...` | `selector: {kind: macro, name: RX_LIMIT}` |
| `enum rx_state { ... };` | `selector: {kind: enum, name: rx_state}` |
| `typedef enum { ... } rx_mode_t;` | `selector: {kind: type_alias, name: rx_mode_t}` |
| `struct rx_context { ... };` | `selector: {kind: struct, name: rx_context}` |

例如已登记源码中的 `RX_LIMIT` 定义占第 8–9 行，对应卡头项为：

```yaml
code_ref:
  - code_id: code-example
    line_start: 8
    line_end: 9
    selector: {kind: macro, name: RX_LIMIT}
```

示例仅说明结构，实际 `code_id`、名称、类型与完整行段必须来自本轮登记和源码核对。具名枚举与 typedef 别名按实际引用对象区分；只知道局部行段时可使用行段引用，但不能为通过检查而去掉计划要求的符号定位或删减 `required_code_refs`。`evidence_version` 是程序根据实际核验片段生成的系统字段，作者不手填；保留未改引用已有的值，不将它复制给新引用或新依据。

## 文档定位与成稿

文档定位使用实际文本行段 `line_start/line_end`、原件物理页 `page_start/page_end`、`section` 或支持的原生 `locator`。例如 DOCX 的 `locator: {kind: paragraph, paragraph: 2}`，PPTX 的 `locator: {kind: slide, slide: 2}`，以及 XLSX 的 `locator: {kind: cell_range, sheet: Sheet1, range: 'A1:D20'}`。PDF 也支持 `page/pages`，DOCX 也支持 `paragraphs/table_row`。已登记文件的不同章节或代码范围可使用多个引用项。

Docling 的 `element` locator 需要 `ref`（如 `#/pictures/0`）、`source_sha256` 和 `profile_sha256`。如用非默认解析配置，在 locator 的 `parser` 中保留对应解析清单的 `profile.options`。分页提取中的局部元素编号不可直接作为正式 PDF 引用，优先用物理页或页段。正式证据使用原件和原生定位，临时图片文件与提取稿行号用于阅读。保留仍有效的旧 PDF 文本行号、DOCX 历史定位和已有 `snapshot_id/evidence_ref/selector`，按相应旧版本解释。

区分设计要求、规范、静态代码观察、测量和建议，标明实际版本和条件。用到代码的段落旁写 `code_id` 和已验证的符号；卡头无符号或有多项相同符号时补行段。符号引用应覆盖核对过的完整符号，局部依据可仅用行段。正文注明代码是导航入口还是支持该段的静态依据。

正常更新旧卡时将仍有效的旧条件、用途、各结论的依据、历史限制和验证要求迁入对应正文，保留稳定 ID、旧锚点、有效快照定位及入链。把仍有效的依赖、替代关系写成正文链接，保留旧别名或搜索词。
