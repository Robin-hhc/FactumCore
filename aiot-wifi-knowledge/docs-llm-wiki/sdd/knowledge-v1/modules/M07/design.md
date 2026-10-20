# M07 代次索引与消费：开发设计

## 接口与依赖

| 模块 | 文件 | 对外接口 | 依赖与边界 |
|---|---|---|---|
| M07 代次索引与消费 | `S/index.py,search.py`；索引 manifest/bodies/active；SearchReceipt | `build_index(channel, frozen_input)` -> 未激活 generation；`activate(expected_active,new)` 条件切换；`search(context)` -> 固定代次候选；`read(generation,card)` -> 同代正文 | 依赖 M01/M05/M06 各 review_mode 的记录；叠加 M08 当前状态。先断言资格过滤再 top-k，local/shared 分开；不写正文、不自动建卡 |

## 本模块拥有的文件与生成规则

| 路径 | 类别 | 开发动作 | 验收要求 |
|---|---|---|---|
| `skills/common/knowledge/_shared/index.py` | F | 沿 CANNBot SQLite documents/postings 机制改造为卡/断言/范围/证据单元；构建正文包、manifest，完成完整性检查再条件激活 | 构建中断继续服务旧完整代；新旧代切换可恢复；丢失证明不伪造通过；shared 只读实际合入树 |
| `skills/common/knowledge/_shared/search.py` | F | 共用 v3 词项/精确项规则；逐断言硬过滤后 top-k；同卡去重；query read 从固定代次正文包取值 | 中文/符号/短查询诊断可复现；错范围不挤占 top-k；拆分 claim 不抬分；切代/改工作区不混读 |
| `skills/common/knowledge/_shared/tests/test_index_search.py` | F | 合成多 Target 卡、部分失效 claim、中文双字/宏/消息 ID、重复 span、切代及索引损坏 | 过滤先于 top-k、claim 拆分不加分、精读同代、旧代不恢复阻断全部通过 |
| `aiot-wifi-knowledge/artifacts/indexes/active.json` | R | 协调器锁内写 local/shared 指针、manifest 摘要和激活状态 | 任一步切换失败只见旧完整代或新完整代 |
| `aiot-wifi-knowledge/artifacts/indexes/<generation_id>/index.sqlite3` | R | 按 §3.3.4 的逻辑表、postings/v3、Claim 硬过滤和计分规则生成 | 错范围/阻断 Claim 不评分；完整性检查通过且可重建 |
| `aiot-wifi-knowledge/artifacts/indexes/<generation_id>/manifest.json` | R | 固定输入、证明、工具/词项版本和载荷摘要 | 相同输入可解释重建；失配输入或丢证明不伪造成功 |
| `aiot-wifi-knowledge/artifacts/indexes/<generation_id>/bodies/<card-id>.md` | R | 与索引从同一解析对象生成，保存原正文与 body_digest | 搜索后修改源卡或切新代，旧请求精读仍是原字节 |
| `aiot-wifi-knowledge/artifacts/receipts/<request_id>.json` | R | 记录真实命中、精读、证据读取、范围及缺口 | 答案每个结论可回到所用代次、Claim、来源和实际证明 |

完整职责与约束字段见 ../../traceability.json，同一路径只有一个主模块。F 为固定实现，D/R/X 是实例、产物或外部入口，P 首发延期；不得手造不存在的业务工程或成功证据。
