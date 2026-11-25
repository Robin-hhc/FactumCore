# 开发和验证指南

本指南承接根目录 [AGENTS.md](../AGENTS.md)。Agent 先读入口规则，再根据改动选择本页场景。生产 CLI、领域 Skill 和知识库使用说明仍由各自目录维护；本页不替代业务知识根的 `AGENTS.md` 和 `config.yml`。

## 标准目录

开发代码留在主仓，环境、可写测试状态和报告放在同级测试根。本机例子是 `E:/FactumCore` 与 `E:/FactumCore-Test`；其他机器可设置 `FACTUM_TEST_ROOT` 或给统一入口传 `--root <绝对路径>`。

```text
<开发仓>/                     # main；只保留必要的活动工作树
  .scratch/sdd/               # 设计、任务状态和必要说明
<测试根>/
  lab.json                    # 本机资源登记；不含凭据，不提交到代码仓
  envs/                       # 平台/版本/依赖锁对应的可复用资源
  fixtures/                   # 一份有来源与摘要的基准原件、附件和最小源码样本
  hosts/dev/                  # 日常联调配置及可写 OpenFlow 数据
  hosts/cold/                 # 用户体验配置及可写 OpenFlow 数据，默认保留
  runs/<run-id>/              # 本轮清单及独立 work 临时状态
  reports/<run-id>/           # JUnit、日志、summary 和必要验收证据
```

默认测试根锚定 Git common-dir 对应的主仓，而不是当前工作树名称。首次初始化只建立目录和登记文件，不下载依赖、不重置宿主、不处理历史目录。

```text
python dev/lab.py init
python dev/lab.py status
```

需要自定义测试根时，以下示例中的 `<测试根>` 替换为绝对路径：

```text
python dev/lab.py --root <测试根> init
python dev/lab.py --root <测试根> status
```

`lab.json` 和宿主 `launch.json` 属于本机配置。共享文档、提交消息和报告不记录 API key、OAuth 内容、密码或访问令牌。

## 复用资源，隔离可写状态

普通验证复用已校验的解释器、Node 依赖、CLI 和 OCR 模型。每轮独立的内容包括：知识根、原件修改副本、卡片、来源登记、SQLite、索引、解析缓存、OpenFlow 设置/会话、端口和安装测试目标。

资源相容性由平台、版本和锁摘要确认。只读使用活动资源，依赖变化时准备新一代；不在其他运行正在使用的环境中执行 pip 升级、npm ci 或模型替换。安装测试使用新的安装目标，不能借用已装依赖来证明安装完整。

### Python

日常使用 Python 3.12；兼容性与发行验证按影响覆盖 3.10、3.11、3.12。每个平台和依赖锁各保留必要解释器，避免每个测试案例建立一套环境。安装依赖使用 [runtime/requirements.lock.txt](../himate/himate-tools/runtime/requirements.lock.txt)。

准备好解释器后登记：

```text
python dev/lab.py register-python --executable <Python绝对路径> --default
```

登记会校验真实版本、平台，并按当前依赖锁核对已安装的生效依赖，同时记录解释器前缀与依赖路径。统一入口 `run` 再次复查，拒绝锁、依赖或路径已变化的资源，并清除会污染目标解释器的继承 Python 路径设置。虚拟环境在新固定路径重建，不直接搬走旧 venv 后假定其绝对引用仍有效。

### Node 和产品资源

用对应 OpenFlow 检出的 package-lock 和 Node 版本/ABI确认依赖。新依赖安装完成后登记；工作树直接引用一份固定实体，不通过其他临时工作树串联多级 junction。

```text
python dev/lab.py register-node --site <OpenFlow检出绝对路径> --executable <node绝对路径> --default
```

源码以固定 Git SHA 定位。Git worktree 共用对象库，但仍会展开 tracked vendor 和模型文件，不能无限创建。机制测试直接使用当前源码和小夹具；真实整包验收才使用完整发布物。不要每轮复制完整 OpenFlow、文档、vendor 或模型分发包。

OCR 模型按实际测试执行账户安装一次。普通宿主使用固定执行账户 `HOME`/`USERPROFILE`；各宿主独立使用 `OPENFLOW_HOME`、`DATA_DIR` 和平台状态目录，避免位置记录或运行 claim 互相覆盖。当前模型安装契约拒绝模型目录链接，不能用 junction 冒充已支持的模型共享。真实 OCR 机制用例可按[验收说明](../himate/himate-tools/evals/README.md#文档转换样本)使用模型输入。

## 验证场景

| 场景 | 资源和状态 | 完成证据 |
|---|---|---|
| 日常算法、CLI、契约 | 当前候选源码、已登记 Python、独立小知识根；选受影响测试组 | 实际选择、JUnit、summary、必要公共接口回归 |
| 文档、Agent 指引、Skill | 核对链接和命令；Skill 使用其 eval，行为变化追加对应真实执行 | 命令契约一致；Skill 触发、决策与输出满足预期 |
| Python 兼容性 | 每版本/平台独立的匹配依赖；各自 tmp 与报告 | 逐项写明 3.10/3.11/3.12 实际执行和跳过情况 |
| CLI、依赖或模型安装/升级 | 新 HOME、prefix、venv；固定包 SHA，可复用下载缓存 | 正式安装链、版本、doctor、升级保全与失败回滚 |
| PDF、MD 配图、OCR | 从 fixtures 选择样本，复用解析依赖和模型，隔离解析产物 | 原件/附件 SHA、定位、缺口、页数、必要图页及阅读结果 |
| 真实模型 ingest/lint | 同版本 CLI/Skills/Workflow，独立知识根与会话，作者和独立 reviewer | 自然节点推进、计划/审阅、最终卡片与来源摘要、索引结果 |
| OpenFlow 页面和冷启动 | 少量固定程序实例与 Node 依赖；dev/cold 各自设置、数据库和端口 | 实际页面交互、后台状态、追问、恢复、引用和浏览器错误 |
| Linux、SSH、Samba | 固定 Linux 执行环境，独立远端 run 根及已核实的映射/权限 | 实际执行端、传输、目录映射、凭据归属与权限结果 |

页面冷启动与安装冷启动分开选择：前者是空应用状态，后者是干净安装目标。不要为了每次首次引导验证都复制全部依赖和模型。

### 日常统一入口

从开发仓根运行，使用登记为默认的 Python；需要指定另一资源时传 `--python <resource-id>`。选择 `--groups` 时传当前测试职责目录名。

```text
python dev/lab.py run --groups ingest query
python dev/lab.py run --groups tooling --profile quick
python dev/lab.py run --groups deploy --jobs 1
```

`quick` 是每组的局部冒烟，`--groups` 是局部范围，均不能报告为全套验收。默认 full 收集所选组的完整测试；跨功能或发行确需全量时再不指定 groups 执行。通过后仅在新增改动、失败或疑点仍未解决时扩大或重复测试。

`--run <id>` 可指定安全的单段运行名，必须尚不存在；省略时自动生成。`--baseline <summary.json>` 只作同环境、同选择的性能比较。能力源码不在工具旁时传 `--capabilities-root <绝对路径>`。

统一入口调用现有 `run_acceptance.py`，报告与临时文件分开，明确启用成功后回收。启动前需要保留整份现场时使用 `--keep-temp`；已结束的失败或保留运行可以设置 pin：

```text
python dev/lab.py run --groups ingest --keep-temp
python dev/lab.py pin --run <run-id>
```

运行中不能更改 pin；不要等到成功回收后才尝试保留已经删除的临时数据。

### 直接调用底层 runner

适用于调试 runner、仅有工具包或调用方已负责环境登记的场景。使用准备好的 Python，报告和临时根都传本次尚不存在的绝对目录：

```text
python himate/himate-tools/evals/run_acceptance.py --groups query --output-dir <新报告目录> --temp-dir <新临时目录> --cleanup-temp on-success
```

`--cleanup-temp` 默认为 `never`，兼容原有取证调用。启用 `on-success` 必须显式传 `--temp-dir`。JUnit、stdout/stderr、summary 保留在 output；pytest basetemp/cache/unittest tmp 写入 temp。失败、超时或退出未确认时保留临时根。查看 `summary.storage` 中的路径、策略和回收结果，不能将测试通过等同于磁盘回收成功。

### OpenFlow 固定宿主

宿主启动配置存于测试根对应 `hosts/<name>/launch.json`，使用 [dev/openflow_host.cjs](../dev/openflow_host.cjs)。先校验，再启动：

```text
node dev/openflow_host.cjs <launch.json绝对路径> --check
node dev/openflow_host.cjs <launch.json绝对路径>
```

配置格式 `schemaVersion: 1`，明确绝对路径 `site`、`home`、`data`、`executionHome`、`python`、`toolkit`、`npmBin`、`codexLauncher`、`stateFile`、`stopFile`；还包括 `port`、仅本机地址 `host: 127.0.0.1`，可选 `codexHome`。不要把密钥写入配置。

`home`/`data` 决定独立 OpenFlow 数据；`executionHome` 决定共享测试账户已安装的 CLI/模型。启动器保留共享执行账户的 `HOME`/`USERPROFILE`，同时按宿主设置以下独立目录：

| 环境项 | 本宿主路径 |
|---|---|
| `OPENFLOW_HOME` | 配置的 `home` |
| `DATA_DIR` | 配置的 `data`，位于本宿主 `home` 内 |
| `LOCALAPPDATA` | `<home>/platform-data/local` |
| `APPDATA` | `<home>/platform-data/roaming` |
| `XDG_STATE_HOME` | `<home>/platform-data/state` |

只隔离 `DATA_DIR` 不够：同一执行账户内的 per-install 位置记录和运行 claim 也需隔离。不要手动把多个宿主的平台状态目录指回共享 `executionHome`。

`codexHome` 沿用本机既有认证入口，不复制或展示凭据。启动器不重置数据或绑定。创建配置中的 `stopFile` 可请求正常关闭；重新启动前移除该控制标记。需要后台启动时使用对应执行端的隐藏后台方式，并记录 PID、端口和状态文件。

宿主预备 CLI 与能力包沿用[正式安装与部署](../himate/himate-tools/docs/DEPLOY.md)。未发布版本从实际验收检出打包；CLI、Skills、Workflow 必须来自同一版来源。检查 `knowledge --version`、实际知识根 doctor 及宿主环境检查，不把源码 CLI 的成功冒充实际安装就绪。

`hosts/cold` 用户体验数据默认保留。准备新体验时新建或采用已确认的数据根，不直接清空旧数据库。普通会话、上传入库工作流和环境面板的行为分别验证。

## 回收与证据

每轮记录源提交、资源引用、测试选择、独立可写目录、PID/状态、pin 与报告位置。报告包含结果、失败/跳过、人工介入、环境和未验证范围。大解析输出或临时快照回收前，先把复现输入摘要、关键产物和必要截图转存到报告目录。

```text
python dev/lab.py clean --run <run-id>
python dev/lab.py clean --run <run-id> --apply
```

第一条仅预览。第二条只处理本工具有所有权登记、已结束、进程不活跃、未 pin 的单次运行，不删除共享资源、宿主、业务知识根或报告。清理和 pin 更改使用同一运行锁，进程探活不向目标进程发送终止信号。需要解除人工保留时先核对用途，再使用 `pin --run <run-id> --release`。

失败保留少量完整复现。可按最近两份和约七天列出整理候选，但当前入口不按 TTL 自动扫删历史目录。活动运行、用户体验、未处理失败、无所有权标记的旧目录、archive 和唯一业务资料均需单独核对。

常驻资源先按 15–25 GiB、临时运行总量约 10 GiB 规划，业务语料和旧归档另算。这是容量目标，迁移后按卷可用空间复核；不是越过 pin 或删除失败证据的阈值。新建完整安装或大语料压力验证前先看 `status`，确认空间、环境复用和回收安排。

## 历史环境采纳与迁移

现有脏 test workspace、用户体验、旧备份和已被引用的依赖先登记、保全，不因标准目录建立而自动搬动或删除。

1. 核对 Git 状态、运行进程、绑定、目录链接和业务文件集合；保存唯一资料、未提交补丁和必要会话备份。
2. 准备并验证新固定资源。旧 Python venv 在新位置重建；Node 引用核对后直接指向固定实体，原目标有引用时保留。
3. 采用已有宿主时保留其数据路径和绑定，或在备份与哈希复核后切换；先做实际就绪检查，再回收已无引用的旧资源。
4. 历史源码快照只有在代码可由 Git SHA/补丁恢复、输入和证据完整后才回收。旧开发 archive 先提取唯一资料，不按目录名称或时间整删。

## 发布与完成

发布按根 [AGENTS.md](../AGENTS.md#开发与验收流程) 执行，维护 main 空库模板和 test 实际样本；没有本轮授权不提交、推送或合入。跨仓联动分别报告目的仓库、分支、PR/提交和验收范围。

完成时应能回答：改了什么；为什么；用什么提交/执行端/版本验证；实际通过、失败和跳过什么；有哪些人工介入或未覆盖范围；临时状态已回收还是因何保留；Git 与业务资料是否仍在授权范围内。
