# hs-knowledge-commit

## 中文介绍

`hs-knowledge-commit` 用于 `himate-knowledge-wifi-mp` 知识库仓的上库收口：把本地改动按固定模板提交，并通过 `git mm upload` 上传 CodeHub CR，最后回显 CR 链接。

它只负责三件事：

1. `git add .`
2. 按固定四行模板 `git commit`
3. `git mm upload . -y` 并解析 `[CR CREATED]` 链接

同步、回退、分支操作不在本 skill 范围内。

固定提交模板：

```
Description:<中文摘要>
DTS:<DTS号>

Team:WIFI
Feature or Bugfix:Feature
```

DTS 单号必须由用户提供，不得编造。首次索取后记录在 `<仓根>/.scratch/hs-knowledge-commit/dts.json`（已被 `.gitignore` 忽略），后续作为默认选项供用户确认。

## 使用方式

在知识库仓根执行（`--repo` 必须是仓根绝对路径）：

```sh
# 读取上次使用的 DTS 单号
python scripts/commit.py --repo /srv/workspace/ut_agent/work_code/himate/himate-knowledge-wifi-mp --show-dts

# 只提交
python scripts/commit.py --repo <仓根> --description "知识库wifi8协议文档入库" --dts DTS2026103123684

# 提交并上传，输出 CR 链接
python scripts/commit.py --repo <仓根> --description "知识库wifi8协议文档入库" --dts DTS2026103123684 --upload
```

Agent 侧流程见 [SKILL.md](SKILL.md)：先读上次单号、用中文向用户确认单号与变更集，再执行提交；用户明确同意后才加 `--upload`。

退出码：`0` 成功；`2` 参数或仓根不合规；`3` 缺少 DTS 单号；`4` 上传输出中未找到 CR 链接；其他非零码透传 git 的退出码。
