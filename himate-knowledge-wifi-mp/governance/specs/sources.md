# Raw 来源捕获契约（T03）

`source_id` 标识逻辑资料；`snapshot_id` 固定实际原始字节、声明版本与提取身份。主件及显式附件分别登记资源和快照，附件变化改变证据包身份。未知版本写 `unknown`，不推断代码 HEAD。

`document capture --knowledge-root K --path docs-raw/specs/文件.md --source-id ID [--declared-version VERSION] [--attachment docs-raw/specs/附件 ...]` 只读取五类 raw 下实际文件。每个输入读取及完成前复查实际路径和内容，失败不发布完整证据包；支持 UTF-8/BOM Markdown/文本主件，其他格式明确不支持。二进制附件不作文本提取承诺。来源中的外链保持资料内容，不访问。

`document load-capture --knowledge-root K --bundle-ref REF --manifest-digest SHA256` 校验清单、对象、提取文本、locator 和资源/快照一致性。即使原件已移走，仍返回被固定的旧字节证据。摘要证明内容一致性，不认证发布者；权限由外部部署承担。

证据保存在 `logs/evidence/<bundle_id>/` 的 manifest.json、objects/<digest>.bin 和 extractions/<id>/{text.txt,locators.json}。bundle_id 固定内容身份；manifest_digest 固定包含采集时间的确切清单。相同输入幂等复用首次完整证据。每个文本 locator 记录原字节与提取字符/行区间，原始 BOM/换行不因提取而改写。清理 .build 不得删唯一恢复证据。

捕获不修改 `governance/sources.lock.yaml`、knowledge 或导航；它不证明来源语义正确。来源锁由明确 ChangeSet 经独立内容复核和固定检查后事务落位。
