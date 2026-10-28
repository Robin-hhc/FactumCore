# FactumCore 知识库系统：待解决问题清单（2026-10-28）

## 1. 【待开发者修复】apply 事务对「已存在文件」的原子替换静默失败，sources.lock.yaml 与 index.md 未落位

### 问题现象

首次 ingest（operation `ingest-hwdl-20261027`）执行 apply 后，transaction journal 标记全部 12 个写入 `installed=True`、status=`committed`，但磁盘上 **6 个「已存在文件」实际保持旧内容**，未更新：

| 路径 | 期望（journal new_digest） | 磁盘实际 | 结果 |
|---|---|---|---|
| `governance/sources.lock.yaml` | cf4b4842…（含 source_id→docs-raw 路径登记） | a175f32a…（空：resources=[] snapshots=[]） | ❌ 未落位 |
| `knowledge/commands/index.md` | 9152edfb…（含 hwdl-tx-command 导航行） | da1ff39e…（13:47 初始化骨架版） | ❌ 未落位 |
| `knowledge/concepts/flows/index.md` | f718fed5… | 006a4f7c… | ❌ 未落位 |
| `knowledge/concepts/protocols/index.md` | b45e60ae… | 95f7fd45… | ❌ 未落位 |
| `knowledge/rules/index.md` | f3b21dad… | 6abe01d8… | ❌ 未落位 |
| `knowledge/commands/hwdl-tx-command.md`（新建） | b34ec8e3… | b34ec8e3… | ✅ 成功 |
| 其余 4 张新建卡 + 处理记录 | 新 digest | 匹配 | ✅ 成功 |

**规律：新建文件全部成功，已存在文件全部失败。**

### 影响

- `governance/sources.lock.yaml` 是空的，**卡片 `sources` 里的 `source_id`（如 `raw:f3f6a07b…`）无法映射到 `docs-raw/` 真实路径**。别的机器拉取上库内容后（无 `.build/`），卡片来源链接无法解析。
- 5 个 `index.md` 导航未更新，新卡不在人读导航中。

### 证据链

- journal：`logs/operations/ingest-hwdl-20261027/journal.json`，status=`committed`，12 条 entries 全部 `attempted=True`、`installed=True`。
- 磁盘内容 == `backups/*.bin`（旧内容），≠ journal `bytes_b64` 解码的新内容；5 个 backup 时间戳 20:45:00.5（apply 时正常备份）。
- 磁盘文件 mtime 13:47（apply 前初始化时间），远早于 apply 20:45。
- `apply-result.json` 只列 writes 路径列表，无逐文件落盘后校验。

### 根因怀疑

`transaction.py` 的 `mutate()` 对每个 entry 执行 `atomic_bytes(target, content)`（tempfile.mkstemp → os.replace → fsync），随后**无条件** `row["installed"] = True`。对「已存在文件」的批量连续替换 + 频繁 `save_journal`(fsync) 在 overlayfs 环境（`/srv/workspace/friday` 为 overlay，`metacopy=on`）下出现静默未持久化，但 `installed=True` 无真实落盘校验，导致 journal 声称成功、磁盘未更新。

> 注：受控单文件复现（对同一文件单独跑同样 atomic_bytes）均成功，未稳定复现，疑似与批量连续替换+fsync 交互有关。

### 建议修复方向

1. `mutate()` 写入后增加**落盘回读校验**：`atomic_bytes` 后立即 `current_digest(ctx, row["path"]) == row["new_digest"]`，不一致则抛错/标记未安装，而非无条件 `installed=True`。
2. 事务 `finish_commit` 前对全部 entries 做最终一致性校验（磁盘 digest == new_digest），任一不满足则 recovery_required。
3. 排查 overlayfs/metacopy 下 `os.replace` + 连续 fsync 的持久化问题；必要时写入后显式 `sync()` 或校验。

### 现场处置（2026-10-27 已做）

已从 journal `bytes_b64`（digest 校验一致）将这 6 个文件修复写回，现 12/12 entries 与磁盘一致。但 **root cause 未消除**，后续 apply 仍可能复现，需开发者修复。

---

## 2. 【环境变更记录】2026-10-28 08:58 规则锁被外部升级

`governance/framework.lock.yaml` 今晨 08:58 被更新，rules_digest 由 `746350bd…` → `0ac65ee2…`，同时 `source_resources.py`、`schemas/registries.yaml`、`specs/sources.md`、evals 测试、docs-llm-wiki 等一批文件被改（非本 ingest 操作）。

影响：旧索引代（rules_digest 746350bd）与当前规则锁不匹配，query 报 `STALE_RULES`，需基于新规则重建索引后恢复。这是设计内行为，非 bug。

---

## 3. 【环境已知项】overlayfs 部署提示

`/srv/workspace/friday` 为 overlay 文件系统（`metacopy=on`），`/srv/workspace` 为 ext4。涉及原子替换/批量写入的 skill 在部署机需关注持久化行为；本机验证请用服务器原生路径而非网络盘映射（后者会触发 UNC `invalid uri authority`）。

