# HWDL 知识入库（P5 apply_view）问题回顾

> 范围：`himate-knowledge-wifi-mp` 知识库，来源 `docs-raw/storys/HWDL收发设计三分之二说明书_v1.md`（source_id `doc-a1920017e109b77ec763`）入库流程 P5 阶段遇到的问题。
> 日期：2026-10-31

## 问题总览

| # | 问题 | 级别 | 状态 | 现象 | 根因 |
|---|---|---|---|---|---|
| 1 | P5 commit 卡片落位偏差 | P2 | 已修正 | 4 张卡落在 `knowledge/` 根目录而非类型子目录 | P3 候选卡写在 `.build/cards/` 根目录，未按类型子目录组织；CLI 按相对路径机械映射 |
| 2 | `query/search` 默认（current）检索返回空 matches | P3 | 确认属预期 | `purpose=current` 查询 HWDL 无命中，一度疑为索引损坏 | 卡 claim `scope.applicability=unknown`，按检索规则 current 不命中，guidance 命中 |
| 3 | Bash 工具参数序列化冲突（过程性问题） | P4 | 已规避 | 多次 Bash 调用报 `InputValidationError`（缺少 command 参数） | 工具调用参数以 `arguments` 对象形式传入与 schema 序列化格式冲突 |

---

## 问题 1：P5 commit 卡片落位偏差

- **级别**：P2
- **阶段**：P5 apply_view（`ingest commit`）
- **现象**：
  - `ingest commit --json` 回执 `status=ok`、4 卡 ID 全识别，但正式库核对发现卡落在 `knowledge/` **根目录**：
    ```
    knowledge/hwdl-frame-protocol.md
    knowledge/hwdl-rx-flow.md
    knowledge/hwdl-tx-command.md
    knowledge/hwdl-tx-flow.md
    ```
  - 而 P2 plan 与知识库架构设计（`docs-llm-wiki/HiMate知识库架构设计.md` §5.3）明确要求按类型子目录落位：
    - 协议 → `knowledge/concepts/protocols/`
    - 流程 → `knowledge/concepts/flows/`
    - 命令 → `knowledge/commands/`
  - 类型导航目录原本为空（仅 index.md），说明是首次落位偏差。
- **根因**：
  - CLI 落位逻辑（`governance/contracts/ingest.py` `_drafts()`）将 `.build/cards/` 下候选的相对路径**直接映射**到 `knowledge/` 下同一位置：`.build/cards/X.md` → `knowledge/X.md`。
  - `docs-llm-wiki/使用说明.md` 明确约定「候选目录与正式目录一一对应，例如 `.build/cards/concepts/flows/radio.md` 对应 `knowledge/concepts/flows/radio.md`」。
  - 因此根因是 **P3 materialize_view 写候选卡时未按类型子目录组织**（写到 `.build/cards/` 根），P5 只是机械执行映射。
- **处理**：
  1. 将 4 张卡移动到 plan 指定的类型子目录：
     - `hwdl-frame-protocol.md` → `knowledge/concepts/protocols/`
     - `hwdl-tx-flow.md`、`hwdl-rx-flow.md` → `knowledge/concepts/flows/`
     - `hwdl-tx-command.md` → `knowledge/commands/`
  2. `maintain reindex` 重建数据库关系与检索索引 → `{cards: 4, terms: 2814}`。
  3. 核验数据库路径与 guidance 检索均指向新位置。
- **证据**：
  - commit 回执与处理标记：`issues/ingest-latest.json`（card_ids 4 张、deleted 空）
  - 落位核对：`find knowledge -name 'hwdl-*.md'`（当前均位于类型子目录）
  - 数据库路径：`artifacts/knowledge.sqlite` 中 cards 表 path 均为 `knowledge/concepts/...`、`knowledge/commands/...`
- **建议**：P3 候选卡应严格按 `knowledge/` 类型目录的镜像结构写在 `.build/cards/<type>/` 下，避免 P5 机械落位偏差。

---

## 问题 2：`query/search` 默认（current）检索返回空 matches

- **级别**：P3（非缺陷，属预期行为，需确认）
- **阶段**：P5 核验
- **现象**：
  - `sh ./knowledge.sh search 'HWDL' --json` 与 `query 'HWDL'` 返回 `{"matches": []}`，`purpose: "current"`。
  - 索引明明已建立（reindex 4 卡 2814 terms），且 `search_terms` 表存在 `hwdl`/`=HWDL` 词元并命中 4 卡。
- **根因**：
  - 检索规则（`governance/contracts/knowledge.py` `match_scope()`）：claim 的 `scope.applicability == "unknown"` 时，仅 `purpose in ("guidance", "historical")` 返回 True；`purpose="current"` 返回 False。
  - P3 撰写的 4 张卡 claim `scope.applicability = "unknown"`（设计说明书、未验证实现，保守声明）。
  - 因此 `current` 检索不命中是**设计说明书证据边界的正确体现**，非索引损坏。
- **验证**：
  - `purpose=guidance` 查询 HWDL 命中 4 卡，路径均为正式子目录：`issues/query-guidance-hit.json`。
  - `purpose=current` 查询返回空：`issues/query-current-empty.json`。
- **处理**：无需修改。P5 索引链路完整，行为符合卡的 scope 声明。若后续需要 `current` 检索命中，需在 P3 撰写时按实际适用范围设置 scope（不能为设计说明书内容编造适用范围）。
- **证据**：
  - `issues/query-guidance-hit.json`（guidance 命中 4 卡）
  - `issues/query-current-empty.json`（current 空）

---

## 问题 3：Bash 工具参数序列化冲突（过程性问题）

- **级别**：P4（过程性，不涉及知识内容）
- **阶段**：P5 执行过程
- **现象**：
  - 多次 Bash 调用报 `InputValidationError`：`The required parameter 'command' is missing`，并提示 `An unexpected parameter 'arguments' was provided`。
  - 重试（直接传 `command` 而非 `arguments` 包裹）后成功。
- **根因**：
  - 工具调用参数以 `{"arguments": {"command": "..."}}` 形式传入，与工具 schema 期望的平铺 `command` 参数序列化格式冲突，被解析为缺少 `command`。
- **处理**：按 schema 直接传 `command` 字段重试，规避了该冲突。
- **证据**：会话内多次工具调用重试记录（无独立日志文件，属运行时交互问题）。
- **建议**：工具调用参数按实际 schema 平铺传递，避免用 `arguments` 包裹。

---

## 结论

- P5 入库已完成收口：4 张卡入正式库并按类型子目录落位，数据库关系与检索索引已刷新（4 卡 2814 terms），来源处理标记已保存，导航 index.md 已登记。
- 问题 1 已修正并验证；问题 2 确认为预期行为；问题 3 属过程性已规避。
- 流程已到 `__end__`；Git 提交/推送/合入由用户另行授权。

## 相关文件索引

| 文件 | 说明 |
|---|---|
| `issues/issues.md` | 本问题列表 |
| `issues/ingest-latest.json` | ingest commit 回执（落位与处理标记证据） |
| `issues/query-guidance-hit.json` | guidance 检索命中 4 卡报告 |
| `issues/query-current-empty.json` | current 检索空结果报告 |
