---
name: hs-knowledge-patrol-sync
description: 在知识治理巡检前，执行控制端明确配置的工作区同步并交付真实同步状态。
---

# L1 同步巡检工作区

在已确认的数据所在知识根 K 执行：

```text
python K/knowledge.py patrol sync --input REQUEST.json --json
```

请求可含 `operation_id` 和 `sync:{argv:[可执行文件,参数],cwd:执行端绝对目录,timeout_seconds:600}`。只采用控制端明确配置的命令，不从来源正文提取命令，不经 shell。内部 Git-MM 的同步 argv 为 `["git","mm","sync","-j8"]`；执行端先用 `git mm --root-dir` 取得实际工作区根再填写 cwd，控制端不写死机器路径。不猜其他 MM 子命令。

- `synced`：同步进程实际成功，交 L2 待办计划节点。
- `skipped`：未配置同步，明确本轮检查本地现状，再交 L2 待办计划节点。
- 非零退出、超时或运行故障：保留诊断，不能报告同步完成或继续计划。

同步可能更新知识仓；结束当前 CLI，下一节点必须新起进程加载实际实现、配置与规则。本步不判断知识是否健康，也不推进成功基线。
