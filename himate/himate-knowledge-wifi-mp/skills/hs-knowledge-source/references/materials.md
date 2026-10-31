# 来源操作

`knowledge source register --input FILE.json --json` 登记实际来源文件。请求包含 `kind`（doc/code）、`path` 和需要时的仓库身份；代码路径按实际配置解析。ID 由 CLI 返回，不根据标题猜测。

代码默认按 UTF-8 读取；实际为 GB18030 时在登记请求中填写 `"encoding":"gb18030"`。编码由来源登记保存，原字节不转码；不要伪造旧快照声明编码。

`knowledge source list --input QUERY.json --json` 查询来源或关联：按来源 ID 查卡、按卡 ID 查所有来源，或按 kind 列出已引用文件。使用返回的真实路径与 ID。

`knowledge source resolve --input SOURCE.json --json` 按来源 ID 和需要的 Git 版本读取原文。恢复只限可用历史中的实际版本；没有提交且没有保存的旧内容无法凭 hash 找回。缺旧版时将缺口交 P2，不冒充已读。

P1 返回的是本次副本和关联卡入口，不要求一次加载全部正文。Git 仅用于按需回看历史，不参与日常变化判定。

`task.source.parsed` 交付本轮文字、Markdown、结构 JSON、原文定位及图片。产物在 `.build/materials/parsed`，与计划、候选一起在 P5 成功后清理；原件和正式卡保留。后续节点使用同一份材料，不能重转后替换已经审阅的依据。

独立回源用 `source extract`，按需指定 PDF 页范围；读取结束用返回的 read_id 执行 `source release`，较长读取先 `source renew`。各读任务使用 `artifacts/source-read/<read_id>/`，不影响当前 `.build` 或其他查询。`source cleanup` 有界回收过期且非转换中的产物。
