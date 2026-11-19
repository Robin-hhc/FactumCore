# FactumCore 开发规范

本文件适用于本仓的开发、Git 发布和真实环境验收。`himate/` 随 HiMate 迁移，仓库分支、发布步骤和本地开发记录集中在仓库根目录范围。工具开发和部署参见 [HiMate 工具文档](himate/himate-tools/docs/README.md)。

## 分支约定

WiFi 知识根位于 `himate/himate-knowledge-wifi-mp/`。

- `main` 存放开发代码、测试和迁移模板。`docs-raw/`、`knowledge/` 保留目录骨架、配套说明和示例配置，来源登记为空。
- `test` 同步 `main` 的开发版本，用于本地及 OpenFlow 验收。源文档和随文附件按目录分类放入 `docs-raw/` 并提交到 `test`。入库复核后，将 `knowledge/` 中的卡片与 `governance/sources.lock.yaml` 一起提交。配套源码样本保存在根目录的 `main/`，对应配置随样本保存。
- Git 提交和推送按本轮授权范围执行。按文件暂存，保留其他任务的本地修改。

## 开发与验收流程

### 在 main 开发和自测

开始前用 `git status --short --branch` 确认工作区和分支，在 `main` 上通过 `git pull --ff-only origin main` 同步。按改动范围运行单元测试，涉及 CLI、安装或 Workflow 时增加对应集成用例。[验收命令](himate/himate-tools/evals/README.md#执行)

自测通过后检查 `git diff --cached` 和 `git diff --cached --check`。开发代码、相关测试、文档及受影响的发行锁随提交更新，确认原件目录、卡片目录和来源登记仍是空库模板。提交后执行 `git push origin main`。

### 将 main 同步到远端 test

从最新的远端 `test` 合并已经推送的 `main`，保留样本提交。下面的命令从仓库根逐条执行，使用尚未占用的临时工作树路径 `.worktrees/test-sync`。

```sh
git fetch origin refs/heads/main:refs/remotes/origin/main refs/heads/test:refs/remotes/origin/test
git worktree add --detach .worktrees/test-sync origin/test
git -C .worktrees/test-sync merge --no-edit origin/main
git -C .worktrees/test-sync merge-base --is-ancestor origin/main HEAD
git -C .worktrees/test-sync diff --exit-code origin/main HEAD -- AGENTS.md himate/himate-tools himate/himate-skills
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

## 本地开发记录

本仓的 SDD 记录放在根目录的 `.scratch/sdd/`，任务草稿和本地验证报告保存在 `.scratch/`。OpenFlow 知识库工作台的联动开发记录见 [OpenFlow PR #29](https://github.com/xmkid/OpenFlow/pull/29)。
