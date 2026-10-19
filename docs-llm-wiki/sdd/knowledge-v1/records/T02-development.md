# T02：项目发现与入口实际读取

状态：verified（首批切片）。范围以 first-slice.md 的 T02 为准；不代表用户级 Skill 已安装、隐式触发已验收或真实 WiFi 工程已接入。

## 实现与接口

- `skills/common/knowledge/_shared/workspace.py` 提供 `resolve_project(path, registry_path, base_path=None, load_context=False, authorization_epoch='local')`。预期失败抛 `ProjectError(ValueError)`，带 `code/message/path`，由公共 CLI 包装结构诊断。
- registry 仅定位有限登记的配置。原字节摘要必须与当前 config 匹配；配置再经过锁定的完整 workspace Schema 和六槽/三 pair 语义检查。不递归扫描本机，不读取 `config.local.yml`，不安装全局规则。
- 请求路径与映射根均解析真实目录，按目录边界匹配；相对请求必须显式给 base；多 workspace 或同层绑定冲突明确失败，嵌套子绑定须显式 `override_nested: true`。
- Git 身份通过只读 subprocess argv 获取实际根、HEAD、origin、git_dir/common_dir；识别 linked worktree 和嵌套 Git 边界。能安全运行 status 时观察 dirty；存在属性命令或子模块时跳过 status，dirty 为 null 并说明原因，项目绑定与入口加载仍可完成。导出目录仅报告实际目录与 `snapshot_status: not_captured`，HEAD/dirty 均为 null；尚无快照核验器时不认可 export 的非空 expected_identity。
- `resolved` 只列出 workspace、领域根和 `knowledge/` 三个 AGENTS 入口；不读取它们正文。`load_context` 实际读取 UTF-8 原字节，回传正文、摘要、字节数与工具读取 trace，全部完成才返回 `context_loaded`。不宣称模型已采纳规则、知识已检索或业务已验证。
- 回执区分代码仓绑定与 Target 候选：只列与代码源有关的候选，`selected_target` 保持 null，未知构建/模块/特性/协议显式列出，不推断三个芯片已经覆盖。
- 返回前重新核对 registry/config、锁与规则内容、已读入口、Git 身份和工具源码摘要。工具摘要组合 `__init__.py/workspace.py/contracts.py/receipts.py/scope.py`，Skill 未执行故 `skill_digest: null`。

## TDD 记录

环境：workspace `.venv`，Python 3.12.14、pytest 8.4.2；最初全局 Python 3.9 仅确认模块缺失，正式记录与最终运行均使用 `.venv`。全部输入为本测试构建的合成文件，领域契约从当前知识仓纯规则复制到临时 fixture，不读业务原件或源码。

1. 先写公共 `resolve_project` 的“任意 cwd、resolved 不读入口正文”行为测试，再执行：观察缺模块 `ModuleNotFoundError`。随后实现解析接口和依赖衔接，首次运行得到 15 passed、1 skipped。
2. 新增“未知配置字段不得接受、锁定 Schema 被改不得接受、实际回执通过 record 契约”用例，执行观察 3 failed / 15 passed / 1 skipped，再接入完整契约校验并对齐回执。
3. 新增上下文读取期间规则、较早入口、Git 身份变化用例，执行观察对应三条竞态约束均失败，再加入整体复查。原 symlink fixture 因 Windows 权限不足曾跳过，之后改用原生目录 junction 备用 fixture，实际验证路径绕出拒绝，不再跳过。
4. 公共 CLI 对中文空格路径的集成测试先观察到 cp1252 输出编码异常和 traceback；交由 CLI 所属任务修复，保留回归测试，不通过设置测试专用 UTF-8 环境绕过问题。

## 验证命令与覆盖

2026-10-19，在开发 workspace 根执行：

```powershell
.venv/Scripts/python.exe -m pytest skills/common/knowledge/_shared/tests/test_workspace.py -q --basetemp=artifacts/test-tmp/t02-final-02
.venv/Scripts/python.exe -m ruff check skills/common/knowledge/_shared/workspace.py skills/common/knowledge/_shared/tests/test_workspace.py
```

结果：**27 passed in 9.80s**，无 skip；Ruff **All checks passed**。最终回执经当前锁定 record 契约验证，中文 CLI 在未设置测试专用 UTF-8 环境变量时成功。合成目录在成功调用前后，文件集合及逐文件原字节保持相同。

用例覆盖：任意 cwd、中文空格、显式相对基准、registry 相对配置定位、目录前缀、失效登记、多 workspace 冲突、嵌套显式覆盖、真实 junction 逃逸、缺入口、真实正文读取、私有覆盖不加载、未知 Target、Git HEAD/dirty/origin/worktree/嵌套仓、缺失路径、完整 Schema/锁、record 回执、读取竞态、公共 CLI 成败协议、未知代码根、导出身份不伪造和成功全目录字节不变。

## P1 复核修复：仓内 fsmonitor 不授执行

独立审阅发现 `GIT_OPTIONAL_LOCKS=0` 不能阻止 Git 执行 `core.fsmonitor`。新增公开接口回归，在独立合成仓配置 `core.fsmonitor='echo triggered > fsmonitor-executed.txt'`，仅允许在测试自己的源码 fixture 内写无害 marker。先执行以下命令，观察 **1 failed**，marker 确实由发现调用生成：

```powershell
.venv/Scripts/python.exe -m pytest skills/common/knowledge/_shared/tests/test_workspace.py::test_project_discovery_never_executes_repository_fsmonitor -q --basetemp=artifacts/test-tmp/t02-fsmonitor-red-01
```

随后给 `_git` 的所有 Git argv 添加 `-c core.fsmonitor=false`，避免顶层及其内部子 Git 继承仓内可执行 monitor；保留 `GIT_OPTIONAL_LOCKS=0`。不依赖用户全局配置，也不修改业务仓的 Git 配置。完整 T02 回归与静态检查：

```powershell
.venv/Scripts/python.exe -m pytest skills/common/knowledge/_shared/tests/test_workspace.py -q --basetemp=artifacts/test-tmp/t02-fsmonitor-green-01
.venv/Scripts/python.exe -m ruff check skills/common/knowledge/_shared/workspace.py skills/common/knowledge/_shared/tests/test_workspace.py
```

结果：**28 passed in 10.66s**，无 skip；Ruff **All checks passed**。该结果验证 fsmonitor 回归，不能外推为任意 Git 可执行扩展均已隔离。

## 追加复核：属性命令、子模块、入口逃逸与 ABA

补充无害实测发现：Git status 可能执行 `filter.*.clean/process`；父 Git status 还可能递归子模块并运行子模块自己的属性命令。fixture 内 marker 均实际生成。先补三个 helper 配置用例、真实 `K/knowledge` junction 逃逸的 resolved/load_context 两模式用例、registry/config 的 A→B→A 两例，执行观察 **7 failed / 28 passed**：

```powershell
.venv/Scripts/python.exe -m pytest skills/common/knowledge/_shared/tests/test_workspace.py -q --basetemp=artifacts/test-tmp/t02-boundaries-red-01
```

实施后的规则如下：

- 所有 Git 调用保持 `-c core.fsmonitor=false`。status 前只读枚举有效配置中的 `filter.*.(clean|process|smudge)`，有非空命令就不运行 status；`dirty: null`、`dirty_status: unavailable_configured_helpers` 并附 reason，`unknown_fields` 包含 `checkout.dirty`。不把常见全局 Git LFS 配置变成整个项目发现失败，不临时更改用户配置。
- 只读 `git ls-files --stage -z` 发现 mode 160000 时不运行 status、不递归探测子仓；返回 `dirty: null`、`dirty_status: unavailable_submodules` 及原因。其余 status 显式带 `--ignore-submodules=all` 作防御。真实根、HEAD、origin 与实际入口仍可完成绑定和读取。
- 每个 required entry 的真实路径须留在其所属的已登记真实根内：workspace AGENTS 属于 W，领域及 knowledge AGENTS 属于 K。初始检查、每次读取前后和最终复核均检查；junction/symlink 越出返回 `ENTRY_PATH_ESCAPE`。此检查是发现契约，不执行 ACL。
- registry/config 均只读取一份原字节，摘要与 `contracts.load_document_bytes` 使用这同一份 bytes；配置匹配必须采用登记摘要绑定的这份解析结果。结束时再比较当前文件原字节。A→B→A 注入不会让 B 的映射绑定到 A 的摘要上。

首个 helper 处理版本会整次拒绝发现；为保留常见全局过滤器下的发现能力，进一步先增加“配置 helper 仍可加载入口但 dirty 未知”和“真实父子 Git 不运行子模块 helper”两例，观察 **2 failed** 后调整为上述 dirty 未知策略：

```powershell
.venv/Scripts/python.exe -m pytest skills/common/knowledge/_shared/tests/test_workspace.py::test_configured_helper_keeps_context_discovery_available_with_unknown_dirty skills/common/knowledge/_shared/tests/test_workspace.py::test_submodule_helper_cannot_execute_during_parent_discovery -q --basetemp=artifacts/test-tmp/t02-dirty-unknown-red-01
```

另外补入最终复核前新建逃逸 junction 的两个模式反例。测试的普通 Git fixture 用空 GLOBAL/NOSYSTEM 配置保持确定性；独立的临时 user gitconfig 用例确认实际外部 helper 配置也会被识别并令 dirty 未知，未通过测试隔离隐藏生产行为。

最终执行：

```powershell
.venv/Scripts/python.exe -m ruff format skills/common/knowledge/_shared/workspace.py skills/common/knowledge/_shared/tests/test_workspace.py
.venv/Scripts/python.exe -m ruff check skills/common/knowledge/_shared/workspace.py skills/common/knowledge/_shared/tests/test_workspace.py
.venv/Scripts/python.exe -m pytest skills/common/knowledge/_shared/tests/test_workspace.py -q --basetemp=artifacts/test-tmp/t02-boundaries-final-02
```

结果：**40 passed in 19.68s**，无 skip；Ruff **All checks passed**。入口初始/末次真实 junction 检查、同字节解析 ABA、普通 Git 身份和 helper/子模块不执行 marker 均有公共接口回归。

观察边界：Git 配置和索引由多个只读命令观察，未原子冻结可能位于外部的配置。这里没有安装沙箱，也不提供对抗配置在检查与 status 之间被恶意并发更改的执行隔离保证。dirty 未知不外推 clean；即使 dirty 被观察为 false，也不替代 T04 的精确来源字节快照。

## 尚未覆盖的义务

本轮没有建立代码内容快照，Git dirty=true 也不等于内容已取证；后续来源模块负责绑定具体字节。用户级 registry/薄规则安装、Skill 自然任务隐式选择、宿主会话加载顺序、授权系统、真实六 Target 构建与业务接入留给对应后续任务。目录与 registry 不是 ACL。回执是本机绑定/读取证明，不自动发布，也不持久化新缓存或改业务文件。
