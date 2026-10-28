# Raw 来源捕获契约（T03）

`source_id` 标识逻辑资料；`snapshot_id` 固定实际原始字节、声明版本与提取身份。主件及显式附件分别登记资源和快照，附件变化改变证据包身份。未知版本写 `unknown`，不推断代码 HEAD。

`document capture --knowledge-root K --path docs-raw/specs/文件.md --source-id ID [--declared-version VERSION] [--attachment docs-raw/specs/附件 ...]` 只读取六类 raw 下实际文件，包括 `docs-raw/troubleshooting/` 的问题定位与排查经验。每个输入读取及完成前复查实际路径和内容，失败不发布完整证据包；支持 UTF-8/BOM Markdown/文本主件，其他格式明确不支持。二进制附件不作文本提取承诺。来源中的外链保持资料内容，不访问。

`document load-capture --knowledge-root K --bundle-ref REF --manifest-digest SHA256` 校验清单、对象、提取文本、locator 和资源/快照一致性。即使原件已移走，仍返回被固定的旧字节证据。摘要证明内容一致性，不认证发布者；权限由外部部署承担。

证据保存在 `logs/evidence/<bundle_id>/` 的 manifest.json、objects/<digest>.bin 和 extractions/<id>/{text.txt,locators.json}。bundle_id 固定内容身份；manifest_digest 固定包含采集时间的确切清单。相同输入幂等复用首次完整证据。每个文本 locator 记录原字节与提取字符/行区间，原始 BOM/换行不因提取而改写。清理 .build 不得删唯一恢复证据。

捕获不修改 `governance/sources.lock.yaml`、knowledge 或导航；它不证明来源语义正确。来源锁由明确 ChangeSet 经独立内容复核和固定检查后事务落位。

正式来源的跨机恢复不依赖生产机的 `.build/` 或证据缓存。配套 `hs-knowledge-source-prepare` 及公共来源函数的来源解析优先核验固定恢复对象；对象缺失时，只能使用正式来源锁中唯一登记的资源位置，并核对原始字节摘要和大小。raw／附件限定在六类 `docs-raw/`，代码文件只能从当前项目配置声明的模块取得；不得搜索同名文件、跟随链接或以新版替代缺失旧版。已登记的固定 Git 原文恢复同样适用于 `code_root`／`modules` 配置，只读本地确切对象，不联网补取。

raw 在 capture 时尚未提交并不妨碍随后随正式资产一起提交。当前文件升级或删除后，可从正式登记路径的本地 Git 历史核对最多 1000 个路径变更提交，按 SHA-256 和大小选取确切旧版；不搜索其他路径、不追随改名、不执行签名验证或联网补历史。历史缺失、浅克隆或搜索范围不足时报告缺口，不重签历史锁或以最新版本代替。

`logs/evidence/{objects,checked-code,extractions,locators}/` 是本机缓存。提取文本与定位图缺失时，从已核验的确切原版按配套适配器重建，输出仍须匹配原冻结指纹；不能复现或旧版不可得时报告未完成，不改写来源锁。显式采用的构建／运行材料及有效限制状态另行保全，不能因忽略缓存而一并丢弃。
