# FactumCore 知识库系统：待解决问题清单（2026-10-27）

> 本文件供另一个开发 agent 接手解决。以**最新版 FactumCore**（`D:\knowledge_graph\FactumCore`，commit `2379f7b`）状态为准，只保留**当前仍未解决**的问题、各自的实际部署背景、根因与当前临时规避方案。已修复/已解决的历史问题不在此列。

## 一、实际部署场景（背景，务必先读）

1. **代码仓布局**：`aiotbot-knowledge-wifi-mp/` 是唯一领域根，**并非一定固定在代码仓根目录**——后续可能被前置文件夹嵌套，例如 `repo/aiotbot/aiotbot-knowledge-wifi-mp/`。`config.yml` 的 `knowledge_roots.wifi` 记录相对 `config.yml` 的相对路径，嵌套时值为 `aiotbot/aiotbot-knowledge-wifi-mp`。
2. **skills / workflows 是能力分发源码，实际会移走**：最新版已将部署工具移到 `aiotbot-knowledge-wifi-mp/tools/deploy/`，skills/workflows 部署到 Agent 自己的目录，按最终位置用 `--register-existing` 登记，运行不要求项目根保留这两个目录。
3. **运行环境**：**Windows电脑和linux服务器都支持运行agent，Windows 电脑上的 agent 需要通过网络盘/ssh访问 Linux 服务器上的代码仓**（`Y:` 映射 `\\7.151.107.107\workcode\...`）。网络盘延迟高 + venv 冷启动慢，跨节点 subprocess 调用实测单次可达 3 分钟+。
4. **运行时依赖**：skill 跨节点调用（如 materialize 调 maintain、index-build 调 apply verify）通过 `subprocess.run(..., timeout=...)` 硬编码超时执行。网络盘环境下默认值偏小。

## 二、当前未解决的问题

### 问题 A：UNC 网络盘 SQLite URI bug（index-build / query 阻塞）★最关键

**背景**：知识库在网络盘（UNC 路径）上，index-build 与 query 读 SQLite 索引失败。

**现象**：index-build 报 `INDEX_READ_FAILED invalid uri authority: 7.151.107.107`；query 同理。

**根因**：网络盘映射 `Y:` 经 `Path.resolve()` 变成 `\\?\UNC\7.151.107.107\...` 扩展路径。
- `governance/contracts/indexing.py:verify_database`（约 117-122 行）先剥离 `\\?\UNC\` 前缀得 `\\server\share\...`，再 `Path.as_uri()` 生成 `file://7.151.107.107/...`；
- SQLite `uri=True` 把主机名 `7.151.107.107` 当 URI authority 拒绝 → `invalid uri authority`。
- 同样问题在 `hs-knowledge-query/scripts/node.py:704`（`db.as_uri()`）。

**验证结论**（Python 实测）：
| URI 形式 | 结果 |
|---|---|
| `file://7.151.107.107/...`（as_uri 产物） | FAIL `invalid uri authority` |
| `file:////7.151.107.107/...`（4 斜杠 + 正斜杠路径） | OK |
| RAW `sqlite3.connect('\\server\share\...')` | OK |
| 本地盘 `C:`（drive-letter） | OK（as_uri 生成 `file:///C:/...`） |

**影响范围**：
- `governance/contracts/indexing.py:122` —— 该文件被 `governance/framework.lock.yaml` 锁定（sha256 固定），**修改后必须同步更新 lock 中的 sha256，并重算 rules-digest**（`framework.lock.yaml` 的 SHA256），否则 `RULE_DIGEST_MISMATCH`。
- `hs-knowledge-query/scripts/node.py:704` —— 不在 lock 内，改完直接生效。

**当前临时规避**（不改代码）：把知识库镜像到本地盘 `C:`（`C:/Users/h00953751/AppData/Local/Temp/hs-test/mirror-wifi`，拷贝 knowledge/governance/logs/.build/operations），index-build/query/query-regression 全部指向镜像跑通。**注意**：改锁文件会连锁改变 rules-digest，导致已提交的 journal/apply-result/ingest-record（绑定旧 digest）全部变 stale（`TRANSACTION_PENDING`）——因此正式修复需规划重跑全链路。

**修复指引（供接手 agent）**：
1. 两处 `as_uri()` 改为：UNC 路径用 4 斜杠 `file:////server/share/...`（正斜杠），非 UNC 保持 `as_uri()`。
2. 更新 `governance/framework.lock.yaml` 中 `contracts/indexing.py` 的 sha256，重算 rules-digest。
3. 因 rules-digest 变化，已提交的 processing records 会 stale，需新 operation_id 重跑 P1→P7（或按治理规则处理旧记录）。
4. 建议在 `tools/deploy/tests/` 补一个 UNC 路径的回归用例。

### 问题 B：`install_catalog.py` 硬编码知识库在代码仓根目录（嵌套部署会失败）

**背景**：知识库可能被前置文件夹嵌套（如 `aiotbot/aiotbot-knowledge-wifi-mp`），但部署工具假定它固定直放仓根。

**现象**：把 `config.yml` 的 `knowledge_roots.wifi` 设为嵌套路径（`aiotbot/aiotbot-knowledge-wifi-mp`）后，运行 `install_catalog.py --register-existing` 报 `INVALID_WORKSPACE_MAPPING`，exit 3，catalog 未生成。

**根因**：`aiotbot-knowledge-wifi-mp/tools/deploy/install_catalog.py:workspace_registration()`（约 328-332 行）硬编码：
```python
if value.get("schema_version") != "2.0" or value.get("knowledge_roots") != {
    "wifi": "aiotbot-knowledge-wifi-mp"
}:
    raise InstallError("INVALID_WORKSPACE_MAPPING")
lock = config.parent / "aiotbot-knowledge-wifi-mp/governance/framework.lock.yaml"
```
- 要求 `knowledge_roots` **精确等于** `{"wifi": "aiotbot-knowledge-wifi-mp"}`（值写死），嵌套时值不同 → 报错。
- lock 路径也写死 `config.parent / "aiotbot-knowledge-wifi-mp/..."`，嵌套时即使过了值校验也会解析到错误位置。

**对照**：运行时 skill（`hs-workspace-explore/scripts/node.py`）已支持嵌套——`roots["wifi"]` 动态读取 + `safe(workspace, ...)` 用 `PurePosixPath.parts` 支持多段相对路径。**问题只在部署工具层**。已实证：flat（无嵌套）注册成功，嵌套注册失败。

**当前临时规避**：嵌套场景下手动绕过 `workspace_registration` 校验（或先把 config 改成 flat 注册完再改回），或用旧版打过补丁的 `install_catalog.py`（工作区 `Y:\friday\work_code` 下有动态读取版本）。

**修复指引（供接手 agent）**：
1. `workspace_registration()` 改为动态读取 `value["knowledge_roots"]["wifi"]`（校验其为安全相对路径：无 `\`、无 `:`、非绝对、无 `..`），lock 路径用 `config.parent / wifi_root / "governance/framework.lock.yaml"`。
2. 建议保留对 `knowledge_roots` 键集合 == `{"wifi"}` 的校验（与运行时 node.py 一致）。
3. 在 `tools/deploy/tests/test_relocation.py` 补一个嵌套（`aiotbot/aiotbot-knowledge-wifi-mp`）fixture 用例。

### 问题 C：跨节点 subprocess 超时偏小（网络盘性能瓶颈）

**背景**：Windows agent 经网络盘访问代码仓，网络盘延迟高 + venv 冷启动慢，跨节点 subprocess 调用实测单次可达 3 分钟+。

**现象**：materialize/verify 等跨节点调用在 `timeout=120` 下失败。

**根因**：skill 脚本内 `subprocess.run(..., timeout=120)` 硬编码（约 17 处，分布在 `skills/common/knowledge/*/scripts/support.py` 及个别 `transaction.py`/`merge.py`/`publish.py`/`recover.py`）。注意 `tools/deploy/install_catalog.py` 内部还有 `timeout=30`（subprocess 校验），属另一类。

**当前临时规避**：批量改 `timeout=120` → `timeout=600`。**注意**：skill 源码改动后必须**重新生成 catalog**（catalog 存的是 skill 副本，旧副本不带新超时）。工作区 `Y:\friday\work_code\skills\common\knowledge\` 下 17 个文件已改（当前 grep 确认 0 处 `timeout=120` 残留）。

**修复指引（供接手 agent）**：
1. 将跨节点调用超时从硬编码 120 提高（如 600），或改为可配置（读 env/request）。
2. 确认覆盖所有跨节点调用点（grep `timeout=120`）。
3. 若改动在 skill 源码，发布后需重新生成 catalog。

## 三、已确认无需处理（设计行为，非 bug）

- **问题 D：`purpose: guidance` 查询**：`governance/contracts/knowledge.py:match_scope`——`purpose in ("current","implementation")` 时要求 `claim.usage == "current"`；纯文档卡 `usage: guidance` 仅 `guidance`/`historical` 目的可见。**这是设计行为**。使用方：query 带 `purpose: guidance`；P7 query-regression 的 target_queries 需显式带 `"purpose": "guidance"`（view 的 target_queries 已支持 purpose 字段）。
- **问题 E：rules-digest 连锁变化**：契约文件受 `framework.lock.yaml` 锁定，改契约 → 需更新 lock sha256 → rules-digest 变化 → 已提交记录变 stale。这是治理设计，不是 bug；修复问题 A 时需规划重跑。

## 四、当前验证状态（供接手 agent 参照基线）

- **ingest P1→P7 全通过**（operation `ingest-hwdl-v3`，新版本流程，真人确认门已移除）：两卡 `hwdl-frame-flow`（flow）与 `hwdl-snap-protocol`（protocol）已落库并登记 `logs/ingest/ingest-hwdl-v3.yaml`。
- **index-build / query 已在本地盘镜像跑通**：gen-02f994d06c68725ebbf838dd，2 docs/2 claims/894 postings；query-regression passed（2 case 全绿）；query 命中两卡（目标卡排首位）。网络盘直接跑仍因问题 A 失败。
- **FactumCore 自带部署测试**：`tools/deploy/tests/` 56 passed / 7 failed（失败为环境项 `DEPENDENCY_UNAVAILABLE` 缺锁定运行时版本、unicode 项，非逻辑失败）。
- **关键路径/身份**：
  - 知识库根（工作区）：`Y:/friday/work_code/aiotbot/aiotbot-knowledge-wifi-mp/`
  - rules-digest（工作区，未改动）：`788c7c8902cfcb7fef63e40f7f02cd66a6d63d1fe11188c0ca780a1d1827c215`
  - 本地盘 venv：`C:/Users/h00953751/AppData/Local/Temp/hs-test/factum-venv2/Scripts/python.exe`
  - 本地盘 catalog：`C:/Users/h00953751/AppData/Local/Temp/hs-test/factum-catalog/catalog.json`
  - 本地盘镜像：`C:/Users/h00953751/AppData/Local/Temp/hs-test/mirror-wifi`
  - 测试文档：`docs-raw/storys/HWDL收发设计三分之二说明书_v1.md`
  - 最新版来源：`D:\knowledge_graph\FactumCore`（commit `2379f7b`）

## 五、建议修复顺序

1. **问题 A（UNC URI）**——最优先，网络盘部署的硬阻塞，改动面明确（两处代码 + lock + 重跑）。
2. **问题 B（嵌套部署）**——影响后续真实仓部署形态，改动小（一个函数动态化 + 补测试）。
3. **问题 C（timeout）**——提升稳定性，改源码后需重新生成 catalog。
