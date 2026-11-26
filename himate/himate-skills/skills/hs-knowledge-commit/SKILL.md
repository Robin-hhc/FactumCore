---
name: hs-knowledge-commit
description: 在 himate-knowledge-wifi-mp 知识库仓内完成上库：按固定四行模板提交变更，并通过 git mm upload 上传 CodeHub CR，回显 CR 链接。适用于用户要求把知识库改动提交上库的场景。
---

# 知识库上库（WiFi 知识库仓）

把知识库仓的本地改动提交并上传到 CodeHub 评审。只做 `git add .` → `git commit` → `git mm upload . -y` 三步，不做同步、回退或分支操作。

## 前置约束

- **必须在知识库仓根执行**：`--repo` 传仓根绝对路径（如 `/srv/workspace/ut_agent/work_code/himate/himate-knowledge-wifi-mp`），脚本不按自身位置反推。
- **DTS 单号只能来自用户**，不得编造。首次向用户索取；之后从本地记录读取并作为默认选项，仍要用户确认。
- **commit message 固定模板**，后两行不变：

  ```
  Description:<中文摘要>
  DTS:<DTS号>

  Team:WIFI
  Feature or Bugfix:Feature
  ```

- **CR 链接只从 `git mm` 输出解析**，不得自行拼接域名。

## DTS 本地记录

默认路径 `<仓根>/.scratch/hs-knowledge-commit/dts.json`（`.scratch/` 已被仓 `.gitignore` 忽略）。可用 `--dts-file` 覆盖。

- 读取：`python scripts/commit.py --repo <仓根> --show-dts`
- 保存：提交成功后脚本自动写入本次使用的 DTS。

## 流程

1. 读取上次单号：`commit.py --repo <仓根> --show-dts`。
2. **用中文向用户提问**：
   - 有记录时：选项「沿用上次 <DTS号>」/「输入新单号」；
   - 无记录时：直接请用户提供 DTS 单号。
3. 生成 `Description`：根据本次实际变更生成一行中文摘要，只替换模板第一行的摘要部分。
4. 展示 `git status --short` 变更集，向用户确认；同时询问本次是否上传（只提交 / 提交并上传）。
5. 执行提交：
   - 只提交：`python scripts/commit.py --repo <仓根> --description "<摘要>" --dts <DTS号>`
   - 提交并上传：追加 `--upload`
6. 上传成功时，把脚本输出的 `[CR] <链接>` 原样回显给用户。

## 禁止与失败处理

- 不执行 `git reset`、`git rebase`、`git pull`、`git push`；同步与分支操作由用户自行决定。
- 不在非仓根目录执行 git 操作。
- 提交或上传失败时原样回显 stdout/stderr，不猜测原因、不自动重试。
- 上传输出中没有 `[CR CREATED]` 链接时按失败处理，回显完整输出。
