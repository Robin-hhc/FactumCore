# 固定 CI 作业契约

`K/check.py` 与 `check.sh` 必须由受保护的作业从可信基线取得；作业固定程序、规则、依赖与接受／拒绝样例。候选提交只能提供卡、导航、来源锁与 `logs/ingest/` 记录。不要从候选 checkout 执行它自己的 check.py，亦不可由候选选择本次规则摘要。

```text
FACTUM_PYTHON=<job-selected absolute Python>
<trusted K>/check.sh --trusted-root <trusted K> --candidate-root <candidate K> --rules-digest <job-pinned SHA> --commit <candidate commit> --input <job-input.json> --output <new external report.json>
```

全部路径须为绝对路径；报告在两个输入树外。job-input 的 `inputs.source_objects` 显式映射 snapshot ID 到确切原版路径；结构化源定位还需固定提取器的确切字节结果。代码卡另外需要真实固定 `code_checkout` 和映射；未知不当成已接入。候选目录中的程序、私人 `.build`、确认事件、安装 catalog 和活动索引不参与检查。

固定脚本只生成临时索引及报告，退出 0/1/2；不执行 Agent、真人确认、修改或入库。作业负责固定 candidate checkout 与声明的 commit 一致，并记录确切原文、业务 checkout 和映射的版本。此仓当前未部署远端 CI 受保护配置；本契约与 fixture 证明接口行为，不代表保护规则已启用。规则变更作为被测对象走独立回归，不能批准同批知识。

旧处理记录按实际采用的正文版本核对，不用更新后的当前卡替换旧卡。检查先使用完整候选视图；需要旧版时，固定脚本只读候选仓同一知识根的 Git 正文对象。历史不完整、对象不可得或搜索范围未完整执行时返回未完成。也可由作业明确提供确切的 Markdown 对象；JSON 字段为：

```json
{
  "inputs": {
    "source_objects": {
      "SOURCE_SNAPSHOT_ID": "E:/job/originals/exact-source.md"
    },
    "historical_card_objects": {
      "REPLACE_WITH_64_HEX_SHA256": "E:/job/history/exact-old-card.md"
    }
  }
}
```

将占位替换为记录中实际的 snapshot ID 和 SHA-256，文件路径必须为绝对路径。旧卡文件按整份原字节核验 hash，再解析 Card ID 与实际 Claim；不加载其中的程序，不接受 JSON Python callback。对象只有正文／hash 身份，不能把它套上调用者请求的路径来证明该路径存在。有验收摘要时还须与其 Card ID／SHA／Claim 一致。完全虚构的目标是阻断错误；缺少必需旧正文是未完成（退出 2）。

相同 `inputs` 可写入手动 lint 的 REQUEST JSON，无需 catalog。正式 `logs/ingest/` 记录检查最终 P7 状态、完整固定清单、真实卡／Claim 引用和处理前驱；P6 的 `.build` 中间记录不按最终状态验收。`pending` 是对象数组；明确 Card/Claim 必须成对并带未解 outcome，普通原件／范围待办不靠自由文本推断成 Claim 限制。
