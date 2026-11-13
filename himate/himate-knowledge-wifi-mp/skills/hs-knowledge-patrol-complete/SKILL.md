---
name: hs-knowledge-patrol-complete
description: 汇总本轮实际处理结果及剩余待办；用于巡检L4。
---

# 报告巡检结果

在实际知识根执行命令，Linux 使用 `sh ./knowledge.sh`，Windows 使用 `.\knowledge.cmd`；已注册入口可直接用 `knowledge`。复用 Workflow 首节点或宿主已确认的知识根与执行端。独立使用时先确认这两项，再读取该知识根的 `AGENTS.md` 和 `config.yml`。

## 执行

运行 `knowledge patrol complete --json`，交付已处理文件、剩余事项和实际错误。

`completed` 表示完成本轮统计，不代表所有来源都已消除欠账；按返回的剩余数量和原因说明。文件成功标记已由各次 P5 保存，本步不另建全库水位或通过凭据。
