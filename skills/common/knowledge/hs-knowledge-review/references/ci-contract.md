# 固定 CI 接口

仅在接入或诊断固定 CI 作业时读取。普通 P4 不配置 CI，也不在本节点提交 Git。

## 可信作业输入

从受保护的可信基线取得知识根内的 `check.py`、`check.sh`、规则与依赖；候选仅提供知识、导航、来源锁及正式处理记录，不能用候选自己的程序批准同批知识。

```text
FACTUM_PYTHON=<作业选择的绝对解释器路径>
<可信知识根绝对路径>/check.sh --trusted-root <可信知识根绝对路径> --candidate-root <候选知识根绝对路径> --rules-digest <作业固定SHA> --commit <候选commit> --input <作业输入.json> --output <新外部报告.json>
```

调用路径为绝对路径，报告位于两个输入树之外。作业固定候选 checkout 与 commit 的一致性，并提供确切原文、代码文件及配置映射。`inputs.source_objects` 映射快照 ID 到确切原版；旧卡使用 `inputs.historical_card_objects:{sha256:absolute_file}`。完整字段以知识根的 `governance/specs/ci-runner.md` 为准。

## 结果边界

固定检查生成临时索引与报告，退出码为 0／1／2；不运行 Agent、不修改或入库、不读取候选私人执行产物。规则变更需要独立验证，未知版本不被模块标签补成已知。

本契约描述可用接口，不表示当前项目已启用远端受保护 CI 或权限隔离。
