# 搜索、精读与来源

## 搜索请求

`knowledge search "关键词" --purpose guidance --json`；复杂请求用 `--input` 提供 `query`、`purpose`、`context` 和 `top_k`。

用途为 current（默认）、implementation、guidance 或 historical。current 要求当前用途和实际范围匹配；implementation 还需实现或测量依据；guidance 是条件内的设计/背景；historical 不证明当前适用。旧卡声明的 Claim 条件继续生效，缺条件不是通配。

新卡若保留结构化 Claim/条件，按声明过滤；只有简洁正文的卡不能因此冒充已核验实现或通用结论。未知条件向用户说明，不猜宏或适用范围。

## 精读

`knowledge read CARD_ID --json` 读取正式卡及来源入口，不要求前序搜索回执。搜索返回独立的 `report_ref`，位于 `artifacts/query/`；使用本次返回值，不读取其他查询的报告。显式 `--output` 在知识根内也只能写 `artifacts/query/`，不能覆盖入库暂存或数据库。

结果按来源声明的实际基准读取：知识根中的原件、项目代码路径，或指定仓库中的文件。旧 Git 版本按实际版本/路径恢复；当前代码位置与历史证据分清。章节、PDF 页和文本行号不混用。

空命中先核用途、真实条件、关键词和诊断。运行错误保持错误，不能当零命中。需重新入库或索引维护时使用相应入口。
