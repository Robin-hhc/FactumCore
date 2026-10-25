# 固定 CI 作业契约

`K/check.py` 与 `check.sh` 必须由受保护的作业从可信基线取得；作业固定程序、规则、依赖与接受／拒绝样例。候选提交只能提供卡、导航、来源锁与 `logs/ingest/` 记录。不要从候选 checkout 执行它自己的 check.py，亦不可由候选选择本次规则摘要。

```text
FACTUM_PYTHON=<job-selected absolute Python>
<trusted K>/check.sh --trusted-root <trusted K> --candidate-root <candidate K> --rules-digest <job-pinned SHA> --commit <candidate commit> --input <job-input.json> --output <new external report.json>
```

全部路径须为绝对路径；报告在两个输入树外。job-input 的 `inputs.source_objects` 显式映射 snapshot ID 到确切原版路径；结构化源定位还需固定提取器的确切字节结果。代码卡另外需要真实固定 `code_checkout` 和映射；未知不当成已接入。候选目录中的程序、私人 `.build`、确认事件、安装 catalog 和活动索引不参与检查。

固定脚本只生成临时索引及报告，退出 0/1/2；不执行 Agent、真人确认、修改或入库。作业负责固定 candidate checkout 与声明的 commit 一致，并记录确切原文、业务 checkout 和映射的版本。此仓当前未部署远端 CI 受保护配置；本契约与 fixture 证明接口行为，不代表保护规则已启用。规则变更作为被测对象走独立回归，不能批准同批知识。

历史卡的 JSON 输入字段为 `inputs.historical_card_objects={sha256:absolute_file}`；固定校验 hash、Card ID 和实际 Claim，不接受 JSON callback。完整输入说明以领域根 `governance/specs/ci-runner.md` 为准。
