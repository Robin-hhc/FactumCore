# 搜索与同代精读 API

## 搜索请求

`query` 默认执行 `search`；也可使用 `python K/knowledge.py search "关键词" --purpose guidance --json`。复杂范围用 `--input` 提供 JSON：

```json
{"query":"问题关键词","purpose":"guidance","context":{},"top_k":5}
```

`operation_id` 可显式固定本次调用；省略时由 CLI 生成并返回。复用项目上下文与实际规则锁即可，不需要 catalog。

| purpose | 采用条件 |
|---|---|
| `current`（默认） | 具有有效当前证据且范围匹配的 current Claim |
| `implementation` | 满足 current 条件，且有实现或测量依据 |
| `guidance` | 背景／设计用途，仍检查证据及声明的范围 |
| `historical` | 所选代次的确切旧证据，可含合格退役内容，不证明当前适用 |

`context` 从问题和已核材料填写。constrained 范围须完整匹配至少一个声明的条件组：chip/side 等标量精确匹配，`features_all` 全部出现，`features_none` 均不出现；缺字段不是通配。unknown 范围只适合 guidance／historical。

背景问题若原本就有芯片／端／特性条件，也要按实填写；不要照抄卡的门槛、猜宏开启或切换用途来制造答案。

## 同代精读

用原搜索的 `receipt_ref` 和命中 `card_id`：

```text
python K/knowledge.py read CARD_ID --receipt SEARCH_RECEIPT --json
```

或以 `query --action read --input` 传 `{"receipt_ref":"实际搜索回执","card_id":"实际命中ID"}`。省略的 channel／purpose／context／generation 沿用原搜索；显式冲突被拒绝。可选 `claim_ids` 仅能是原命中合格 Claim 的非空子集。

读取依据是原搜索回执，不是 read 回执或评估结果。活动代切换后，原搜索仍固定原代次；确切卡或回执依赖已不可用时保持诊断并重新查询，不猜历史关联。没有 `receipt_ref` 的底层 read 读取当前活动代，不能声称同代精读。

## 卡与返回字段

`search` 返回卡身份、合格 `claim_ids`、允许显示的标题／摘要、分数和 `receipt_ref`；`read` 返回该次合格 Claim 正文。`path` 是相对 K 的逻辑卡路径，`card_ref` 指向所选代次的确切卡。逻辑路径可能已经是新版，回答原搜索时使用原回执与同代内容。

返回的 `source_links` 提供来源地址，未内嵌原件全文或原始字节。打开完整卡或链接不扩大原查询用途及合格 Claim 集合。

命中同源背景卡不等于已有答题依据。相关主题未蒸馏时，可沿固定来源查找原文相关章节，不局限于卡内已提炼的段落；明确区分新增原文依据与已索引 Claim。原文仍不足时报告未覆盖范围，不从搜索词或分数推导答案。

## 来源地址与代码入口

每条链接将固定 `evidence` 与可取得的 `current` 分开。按地址的 `base` 解释 `path`：

| base | 路径基准 |
|---|---|
| `knowledge_root` | 实际 K |
| `workspace` | 实际 config.yml 选定的项目根 |
| `repository` | `repo_id` 对应的已配置仓／模块范围 |
| `git` | 确切本地 commit 的仓内路径；代码另带 repo_id，raw省略时用项目Git |
| `absolute` | 执行端实际可读的 dbox 原生绝对路径，不拼到 K 下 |

K 的父目录不一定是项目根。页、段落、表格行与源码行段按原件格式读取，不能把 PDF 页号当提取文本行号。需要完整旧版解析时，使用卡内确切来源绑定与 source 的恢复能力。

代码链接的 `navigation_status` 为 resolved／missing／ambiguous／unavailable；未声明符号的旧来源可为 not_applicable。只用实际返回的当前路径与定位：缺当前文件时为 null，歧义地址没有定位。`current_source_matches` 表示当前整文件是否匹配固定证据，缺当前地址时为 null；符号存在不等于 Claim 当前仍成立。

dbox 的固定证据可保留在正式对象中；本机映射不可读时，当前地址可能为空。query 内部重新核资格、来源、符号和当前字节，Agent 无需复现这套实现检查。链接只说明位置，回答需注明实际读过什么。

## 空命中与运行问题

先核用途、真实范围、关键词和响应诊断。空 `matches` 或空 `gaps` 不证明资料不存在；截断也不能当完整召回。需要调整条件时应有用户问题或实际材料依据。

缺索引、规则变化、来源解析超时等保持真实阻断，不当成有效零命中。规则升级后的旧回执不能通过改签继续使用；缺必要代次或依赖时重新查询。普通查询不自动入库、建图或重建索引，索引维护作为明确的独立任务处理。
