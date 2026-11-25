# FactumCore 开发规范

本文件是 Agent 进入本仓后的开发入口，适用于开发、验证、环境管理和 Git 发布。按任务读取下级 `AGENTS.md`；环境与场景细节见[开发和验证指南](docs/DEVELOPMENT.md)，产品安装见 [HiMate 工具文档](himate/himate-tools/docs/README.md)。开发规范不随业务 Skill 部署到领域知识库。

## 开始前

1. 用 `git status --short --branch` 确认分支和已有修改，保留其他任务的代码、原件、卡片及来源登记。在 `main` 上执行 `git pull --ff-only origin main`；已有修改阻碍更新时先确认归属，不使用 reset、clean 或 stash 掩盖现场。
2. 用 `python dev/lab.py status` 查看已登记环境，再按下表选择验证范围。默认测试根是主仓同级的 `<主仓名>-Test`；自定义时使用 `FACTUM_TEST_ROOT` 或 `--root <绝对路径>`，不要在每个工作树下另建一套测试根。
3. 沿用平台、解释器版本及依赖锁匹配的资源。普通验证只新建可写状态，不逐轮复制完整仓库、vendor、OCR 模型或 Python 环境；安装/升级验证才使用干净安装目标。工作树的 Node 依赖直接引用已登记实体，不串联多级目录链接。OpenFlow 使用统一宿主启动器，同时隔离应用数据和每宿主的平台状态目录。

## 选择验证场景

| 改动 | 至少完成 |
|---|---|
| 文档、Agent 指引 | 检查链接、命令与当前实现；涉及 Skill 行为时运行相应 eval |
| 算法、CLI、契约 | 受影响测试组及相关集成；默认使用已登记 Python 3.12 |
| 安装、依赖、发行 | 干净 HOME/prefix/venv 的安装/升级验证；需要时覆盖 Python 3.10/3.11/3.12 |
| 解析、Skill、Workflow | 对应机制测试；内容/节点行为变化增加真实材料、真实模型执行与独立审阅 |
| OpenFlow、SSH、Samba | 对应实际宿主/页面/执行端验收，单独记录版本和边界 |

日常优先 `python dev/lab.py run --groups <受影响组>`；`quick` 是局部冒烟，`full` 也只证明其实际执行层级。测试通过后，只有新增变更、失败或尚未解决的疑点才扩大或重复验证。隔离脚本通过、真实材料解析、模型工作流、真实页面和远端权限分别报告，不能互相替代。具体矩阵和命令见[开发和验证指南](docs/DEVELOPMENT.md#验证场景)。

## 分支约定

WiFi 知识根位于 `himate/himate-knowledge-wifi-mp/`。

- `main` 存放开发代码、测试和迁移模板。`docs-raw/`、`knowledge/` 保留目录骨架、配套说明和示例配置，来源登记为空。
- `test` 同步 `main` 的开发版本，用于本地及 OpenFlow 验收。源文档和随文附件按目录分类放入 `docs-raw/` 并提交到 `test`。入库复核后，将 `knowledge/` 中的卡片与 `governance/sources.lock.yaml` 一起提交。配套源码样本保存在根目录的 `main/`，对应配置随样本保存。
- Git 提交和推送按本轮授权范围执行。按文件暂存，保留其他任务的本地修改。

## 开发与验收流程

### 在 main 开发和自测

按上述场景完成自测。统一入口将报告放入测试根的 `reports/<run-id>`，临时状态放入 `runs/<run-id>/work`；需要直接调用底层 runner 时，显式分开 `--output-dir` 和 `--temp-dir`。[验收命令](himate/himate-tools/evals/README.md#执行)

自测通过后检查 `git diff --cached` 和 `git diff --cached --check`。开发代码、相关测试、文档及受影响的发行锁随提交更新，确认原件目录、卡片目录和来源登记仍是空库模板。提交、推送和合入均以本轮用户授权为准；获得发布授权后执行对应步骤，不能把自测通过当作发布授权。

### 将 main 同步到远端 test

从最新的远端 `test` 合并已经推送的 `main`，保留样本提交。下面的命令从仓库根逐条执行，使用尚未占用的临时工作树路径 `.worktrees/test-sync`。

```sh
git fetch origin refs/heads/main:refs/remotes/origin/main refs/heads/test:refs/remotes/origin/test
git worktree add --detach .worktrees/test-sync origin/test
git -C .worktrees/test-sync merge --no-edit origin/main
git -C .worktrees/test-sync merge-base --is-ancestor origin/main HEAD
git -C .worktrees/test-sync diff --exit-code origin/main HEAD -- AGENTS.md dev docs himate/himate-tools himate/himate-skills
git -C .worktrees/test-sync diff --name-status origin/test HEAD -- .gitignore himate/himate-knowledge-wifi-mp main
```

确认开发文件已对齐、原有原件、卡片、来源登记和样本配置已保留。合并有冲突时，按 `main` 对齐开发文件并保留测试数据，完成合并提交后复查。检查通过后发布合并，再移除临时工作树。

```sh
git -C .worktrees/test-sync push origin HEAD:refs/heads/test
git worktree remove .worktrees/test-sync
```

推送期间远端 `test` 发生更新时，重新 fetch，从更新后的 `origin/test` 创建临时工作树并复查合并结果。

### 在独立 test 目录验收

在单独保留的验收目录确认当前分支为 `test`，核对本地改动后逐条执行。

```sh
git status --short --branch
git pull --ff-only origin test
git rev-parse HEAD
```

在实际宿主或 SSH 执行端更新需要验证的 CLI 和能力包。验收尚未发布到 npm 的 CLI 时，从本次检出打包，能力包从同一份 `himate-skills` 部署。以 `knowledge --version` 和 `knowledge doctor --knowledge-root "<验收知识根>" --json` 核对实际版本、知识根和依赖。验收 OpenFlow 时重启宿主，绑定这份检出的知识根，运行环境检查并记录宿主版本。[安装与部署](himate/himate-tools/docs/DEPLOY.md)

用实际样本验证受影响的场景，记录 `main` 和 `test` 提交、执行端、运行版本、步骤和结果。代码、Skill 或 Workflow 有问题时回 `main` 修复，从自测、推送和同步重新走一轮。环境问题在对应执行端修复后复测同一版本。

## 收尾与本地记录

- 成功验证先保存报告和必要证据，再回收本轮临时状态；失败保留复现。启动前需要保留现场时用 `run --keep-temp`，已结束运行可用 `pin`；运行中不修改 pin。`clean --run <id>` 默认预览，明确 `--apply` 才清理有本工具登记、已结束且未 pin 的运行。
- 活动运行、共享依赖、宿主数据、正式知识库、旧开发备份和没有所有权标记的历史目录不由运行清理命令删除。迁移或清理这些目录前，核对精确路径、运行引用、Git 状态及唯一资料；保留未提交修改。
- 报告写明代码提交、执行端、依赖与模型版本、场景、结果、跳过/失败、人工介入和未验证范围；指向被回收目录的证据先转存到报告目录。结束前确认临时目录的回收或保留原因，以及 Git 改动范围。

SDD 设计和任务说明放在 `.scratch/sdd/`，其中不保留完整运行环境；可复用资源与验证产物按[标准目录](docs/DEVELOPMENT.md#标准目录)管理。OpenFlow 知识库工作台联动开发记录见 [OpenFlow PR #29](https://github.com/xmkid/OpenFlow/pull/29)。
