# HiMate 知识库入库问题总结（P2 阻塞）

> 生成时间：2026-11-02　执行节点：plan_change（P2）　执行者：代码实现（coder）
> 来源：`docs-raw/protocols/P80211be_D7.0_Aug2024.pdf`（IEEE 802.11be D7.0 / Wi-Fi 7 EHT 标准，1089 页）
> 来源 ID：`doc-ab5477ab787c6b94a654`　SHA256：`cb13afe730f8bc56b531054cd3c1117808c4f846e41f21d49cb7e7a1642f6966`

---

## 1. 结论（TL;DR）

本轮新增 PDF 来源在 **P1 扫描阶段即存在工具链层确定性缺陷**：全量解析 1089 页后解析产物 **259MB**，超过 `max_output_bytes` 的 **256MB（268435456 字节）硬上限**，导致：

1. `prepare_pdf` 抛 `PARSE_OUTPUT_LIMIT`（ContractError，`document_parser.py:736`）；
2. `task.source.parsed = null`，`task.pdf_review` **缺失**；
3. P2（plan）无法按 skill 要求获得 `pdf_review`/`page_index_ref` 候选材料 → **必要依据不足**；
4. 即使强行制定 plan，**P4/P5 的 `_pdf_batch` 也会因缺 `pdf_review` 报 `PDF_REVIEW_REQUIRED` 硬失败**（`ingest.py:352`）。

**处置建议：本文件走 `deferred` 出口**（必要依据不足，不标处理完成），并在工具链修复后重跑。工具链修复方向见 §4。

---

## 2. 问题定位（根因链）

```
prepare_pdf 全量解析 1089 页 PDF
   └─> 产物 document.json 189MB + locators.json 70MB + document.md 5.5MB + text.txt 3.4MB ≈ 259MB
   └─> 超过 max_output_bytes = 268435456 (256MB) 硬上限
   └─> document_parser.py:736 raise ContractError("PARSE_OUTPUT_LIMIT", ...)
   └─> 异常被 ingest.scan 的 except (ValueError, UnicodeError, ImportError, ContractError) 捕获 → 记入 gaps
   └─> _prepare_pdf_review 因异常中断 → task.pdf_review 未赋值（None）
   └─> prepare_pdf 在写 manifest.json 前中断 → task.source.parsed = null
   └─> 解析产物目录成为“孤儿/不完整”缓存（有 document.json/md/text/locators，无 manifest.json）
```

### 关键证据（实测量）

| 项 | 值 | 来源 |
|---|---|---|
| 解析产物总大小 | **259M** | `du -sh artifacts/ingest/parsed/3758691f...-64e4b5f8.../` |
| document.json | 189,229,723 B (~181MB) | `ls -la` |
| locators.json | 73,036,864 B (~70MB) | `ls -la` |
| document.md | 5,719,961 B | `ls -la` |
| text.txt | 3,470,190 B | `ls -la` |
| images/ | 4KB（无位图，pictures 仅为元数据） | `ls -la` |
| 缺 manifest.json | 确认缺失 | 目录列表 |
| task.source.parsed | `null` | `.build/task.json` |
| task.pdf_review | 缺失 | `.build/task.json` |
| task.gaps | `["PARSE_OUTPUT_LIMIT: Parsed materials exceed max_output_bytes (artifacts/ingest/parsed/...3758691f...-64e4b5f8.../...)"]` | `.build/task.json` |
| 契约代码 | `document_parser.py:736`（PARSE_OUTPUT_LIMIT）`ingest.py:352`（PDF_REVIEW_REQUIRED） | `governance/contracts/` |
| runtime 版本 | `0.16.1`（doctor 正常） | `knowledge.sh doctor` |
| docling 版本 | `2.145.0` | source-read manifest |

---

## 3. 已排查的工具链限制（不可绕过）

| 尝试方向 | 结果 | 依据 |
|---|---|---|
| `max_pages` 调小 | ❌ 无效：`max_pages` 是 docling 硬校验（设为 <1089 直接转换失败，非截断） | P2 调查（历史会话） |
| `images_scale` 调小 | ❌ 无效：document.json 中 pictures 为**元数据非位图**，images/ 仅 4KB，减不下 259MB | P2 调查（历史会话） |
| 调大 `max_output_bytes` | ❌ 无效：上限**硬编码 268435456**，无法通过配置调大 | source-read manifest `options.max_output_bytes` |
| `scan` 传 `page_range` | ❌ 无效：scan 不支持 page_range | P2 调查（历史会话） |
| **`source extract` 按页读取** | ✅ **可用**：支持 `page_range` 独立按页解析，产物含完整 manifest（`parse_status: partial`），可作读取材料途径，**但不写 task.pdf_review** | 已实测：1-10 页、1-55 页均成功 |

> 实测 source extract 产物：`artifacts/source-read/48f74583.../`（页 1-10，manifest 758KB）与 `artifacts/source-read/ed0acc44.../`（页 1-55，manifest 4.7MB）。每页平均约 90KB 输出 → 1089 页全量约 98MB，理论可分段解析成功。**但该路径只解决“读取材料”，不生成 P4/P5 所需的 `task.pdf_review`。**

---

## 4. 修复方向（工具链层，需 P1/runtime 侧处理）

1. **调大 `max_output_bytes`**：放开硬编码 256MB 上限（或改为可按来源配置）。
2. **拆分来源 / 分段解析**：让 `scan`（或 `_prepare_pdf_review`）支持 `page_range` 分段解析，逐段生成 pdf_review 候选（如每 100-200 页一段）。
3. **放宽 `max_pages` 校验语义**：将“<1089 直接失败”改为按 `page_range` 截断解析。
4. **`source extract` 补写 pdf_review**：让独立按页读取路径同时登记 `task.pdf_review`，使 P4/P5 可放行。

> 当前 `governance/contracts/` 为 digest-locked 契约（`document_parser.py`、`ingest.py`），改动需走契约更新流程，不能直接改。

---

## 5. 库内现状（无 PDF 先例）

- catalog 仅 2 个来源：1 个已处理 md（HWDL 收发设计说明书）+ 本轮未处理 PDF；4 张知识卡均 HWDL 相关，`protocols` 分类为空。
- 本轮来源 `change=added`、`processed=false`、**无关联旧卡**（`.build/cards/` 为空）。
- 属首次入库，无旧卡可更新/合并/拆分；因材料缺失，P2 无法完成六决策与 `source_pages` 完整评估。

---

## 6. 相关工作区异常（附注）

- 曾出现外部删除：`knowledge.cmd`、`deploy.ps1` 曾被 git 标记 deleted，`governance/sources.lock.yaml` 被修改（P1 合法来源登记）。曾致 CLI `RUNTIME_UNAVAILABLE`，后续命令恢复正常。
- 当前 git 状态：分支 `br`，领先 `origin/master` 1 commit；工作区未暂存修改：`deploy.ps1`、`governance/sources.lock.yaml`、`knowledge.cmd`（见 `git status`）。
- 最近提交：`c5a1339`（知识库协议文档入库与相关流程调整，DTS:DTS2026103123684）。

---

## 7. 相关日志与产物位置

| 内容 | 路径 |
|---|---|
| 本总结 | `ISSUE_SUMMARY.md`（工作区根目录） |
| 会话摘要 | `/home/h00953751/.openflow/data/conv_1793621889689_i31aymznw/session-summary-1.md` |
| 会话历史 | `/home/h00953751/.openflow/data/conv_1793621889689_i31aymznw/session-history-1.md` |
| AI 决策日志 | `/home/h00953751/.openflow/data/conv_1793621889689_i31aymznw/log/ai-decisions-2026-11-02.log` |
| task 材料 | `himate/himate-knowledge-wifi-mp/.build/task.json` |
| 来源副本 | `himate/himate-knowledge-wifi-mp/.build/materials/current.pdf` |
| 全量解析产物（不完整） | `himate/himate-knowledge-wifi-mp/artifacts/ingest/parsed/3758691f...-64e4b5f8.../` |
| source extract（1-10 页） | `himate/himate-knowledge-wifi-mp/artifacts/source-read/48f74583.../` |
| source extract（1-55 页） | `himate/himate-knowledge-wifi-mp/artifacts/source-read/ed0acc44.../` |

---

## 8. 待办与后续

- [ ] P2 提交 `deferred` 出口，说明缺口（本文件即缺口说明）。
- [ ] 工具链修复（§4）后重跑 P1 scan → P2 plan → P3 materialize → P4 review → P5 apply。
- [ ] 确认 `knowledge.cmd`/`deploy.ps1` 被外部删除的原因（可选排查）。
