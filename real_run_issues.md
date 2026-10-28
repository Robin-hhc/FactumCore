# FactumCore 知识库系统：待解决问题清单（2026-10-28）

## 1. 【已补回读保护，现场底层原因待复现】apply 事务对「已存在文件」的原子替换静默失败，sources.lock.yaml 与 index.md 未落位

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

### 开发侧修复边界（2026-10-28，本地补丁）

已补逐目标写入／删除后回读、提交前完整写集校验，以及恢复／回滚的实际字节核对；不一致保留恢复状态，不再仅凭系统调用返回值设置成功。永久故障注入回归见 `skills/common/knowledge/hs-knowledge-apply/tests/test_apply.py`。本机未复现 overlayfs 底层现象，不能据此认定其根因，也不把回读校验扩大为断电持久性保证。

---

## 2. 【环境变更记录】2026-10-28 08:58 规则锁被外部升级

`governance/framework.lock.yaml` 今晨 08:58 被更新，rules_digest 由 `746350bd…` → `0ac65ee2…`，同时 `source_resources.py`、`schemas/registries.yaml`、`specs/sources.md`、evals 测试、docs-llm-wiki 等一批文件被改（非本 ingest 操作）。

影响：旧索引代（rules_digest 746350bd）与当前规则锁不匹配，query 报 `STALE_RULES`，需基于新规则重建索引后恢复。这是设计内行为，非 bug。

---

## 3. 【环境已知项】overlayfs 部署提示

`/srv/workspace/friday` 为 overlay 文件系统（`metacopy=on`），`/srv/workspace` 为 ext4。涉及原子替换/批量写入的 skill 在部署机需关注持久化行为；本机验证请用服务器原生路径而非网络盘映射（后者会触发 UNC `invalid uri authority`）。

---

## 4. 【开发侧已复现并补修】仅拉取共享资产后，来源恢复仍依赖本机缓存

公开 CLI 合成 ingest 后只提交共享资产，再真实 Git clone；消费副本不含 `.build/`、`artifacts/`、`logs/operations/`、`logs/evidence/`。旧实现正式 lint 报 `SOURCE_INPUT_UNAVAILABLE`：新模块配置禁用了 raw Git 恢复，普通快照只读被忽略的原件对象，未闭合“来源锁＋正式原件”的消费路径。扩展到 PDF/DOCX 还发现 native 页／段落定位未接入固定检查，部分文档在生产端 apply 就被阻断。

本地补丁按正式锁的唯一资源位置恢复原字节并核对 SHA-256 和大小；raw 当前文件升级后，只在登记路径的有界本地 Git 历史中找回确切旧版。固定文档适配器由捕获和检查共用，提取／定位缓存缺失时重建并核对冻结指纹；返回实际恢复位置。缺历史、原版或适用代码／构建材料时仍报告缺口。

`.gitignore` 同步排除本机事务目录和四类证据缓存。`logs/ingest/`、`logs/events/` 以及显式采用的构建／运行材料仍是业务资产，不能整体删除 `logs/`。已有未完成事务或未知执行结果时先恢复，不能用删缓存代替处理。详设现有 §5.7／§5.9／§6.4 已补保存边界与换机步骤。

永久验证入口：`himate-knowledge-wifi-mp/evals/tests/test_clean_clone.py`、`test_snapshot_checkout_recovery.py`、`test_git_asset_boundary.py`。测试区分 ingest 前原件已／未提交、原件后续升级、浅克隆缺历史、静态代码模块及有效使用限制；配套能力和运行依赖仍须在消费端可用。该验证不等于现场 overlayfs、另一账号权限或真实宿主验收。

最终本机隔离验收19组：1107通过、1项因账号symlink权限跳过，零失败／错误；其中7个实际Git clone场景全部通过。部署端需更新配套能力和规则，并重建、验证及激活索引；本记录不表示现场部署或overlayfs底层问题已完成验收。

