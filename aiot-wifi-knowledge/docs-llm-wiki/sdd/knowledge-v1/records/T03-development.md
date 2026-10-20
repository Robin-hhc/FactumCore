# T03 raw 原件捕获、附件与持久恢复

状态：implemented / verified（本文首发文本切片）；原始 T03 中 PDF/OCR、真实业务原件的抽取验收不在本次能力内。所有用例均为本测试构造的合成材料，不读取业务原件、源码或 gold，不执行网络抓取、工具安装、Git 提交或发布。

## 接口及实际实现

`S/sources.py` 提供 `capture_document(knowledge_root, path, *, source_id, declared_version='unknown', attachments=None) -> dict` 与 `load_capture(knowledge_root, bundle_ref, manifest_digest=None) -> dict`。预期失败抛 `SourceError(ValueError)`，带 `code/message/path`。返回 `schema_version/bundle_id/bundle_ref/manifest_digest/source_id/identity/resources/snapshots/members`；每个 member 含 `raw_path/source_id/snapshot_id/object_digest/bytes/mime/encoding/object_ref/extraction/text/locators`，二进制附件的最后三项为空。`resources/snapshots` 与 schema_version 可构成现行 sources 契约下的锁增量，本接口不修改来源锁。

- 主原件仅支持 `docs-raw/{conventions,chips,storys,specs,protocols}` 内 `.md/.txt`、有效 UTF-8（可带 BOM，无 NUL）；保留原始 CRLF 和字节，BOM 只从派生文本去掉。未配置 PDF/OCR/Office 解析器，因此相应主文档明确 `UNSUPPORTED_DOCUMENT_FORMAT`；非法文本明确 `UNSUPPORTED_ENCODING`，不产生成功快照。
- 附件必须显式列出，逐件保留原对象及独立 SourceResource/SourceSnapshot。Markdown 内本地 inline/reference/HTML `href/src` 引用必须真实存在且在显式集合内；仅章节 fragment 是导航，代码块、行内代码和 HTML 注释内示例不当附件；远端链接留作文本，不取回。二进制附件仅保留原件，`extraction.status=not_required`，不声称有文本/OCR/页码。
- 控制文件、sources 区、URL、仓外原件、原始参数父级穿越及链接绕出均拒绝；路径按实际目录解析，不按字符串前缀接受。输入只读，来源内指令只作为普通文本。
- 对同一份已捕获原字节计算摘要、解析和生成 locator，记录字节区间与派生 Unicode 字符/行区间及 Markdown 标题上下文；读取前后和整体完成前重新核对真实路径、文件身份/时间/大小和字节，原件或附件变动明确 `SOURCE_CHANGED`。
- 仅写 `K/logs/evidence/<bundle_id>/manifest.json`、`objects/<digest>.bin`、`extractions/<id>/text.txt` 和 `locators.json`，不写 `.build`、knowledge、sources.lock 或 index。目录身份绑定实际来源/附件集合、版本、对象及提取信息；原清单不自 hash，由返回的 `manifest_digest` 固定。
- 同身份捕获使用排他 lock、私有 staging 与整目录 rename 发布；并发同身份返回 `CAPTURE_BUSY`，不覆盖已存对象。既有 bundle 必须先通过完整恢复核验，损坏不自修复/覆盖。写入失败清理本次 staging 和 lock，返回 `EVIDENCE_WRITE_FAILED`；原件始终只读。
- 恢复只依赖 retained bundle，不依赖原 raw 仍存在。重新核对清单身份及锁定 sources Schema、所有原对象摘要/大小、派生文本与 locator 摘要及实际再提取一致性、SourceResource/Snapshot 的字段对应；拒绝缺对象、篡改、失配、逃逸及不完整集合。所有返回的证据引用为相对路径。
- Windows 摘要树易超过 260 字符，内部使用 extended path；对外始终是安全相对引用，不要求用户全局启用长路径。

调用方应始终保存并向恢复接口传入 `manifest_digest`，以固定包含实际 acquisition 时间的确切清单字节。省略外部 pin 时，仍验证内容身份、载荷和语义一致性，但 acquisition 时间仅是清单自述，不可据此认证历史时间或发布人。摘要与路径规则不是访问控制；不声称冻结恶意并发写进程或实现断电后文件系统事务。进程异常留下的 stale lock 不自动删除，应由治理/人工确认恢复，不能抢占其他仍在工作的捕获。

## TDD 与审查修复

环境：workspace `.venv`，pytest 8.4.2；命令从开发 workspace 根执行。先写公共 capture/load API 用例，再创建实现，没有以私有辅助函数重复实现作为主要验收。

1. `t03-red-01`：测试导入不存在的 `_shared.sources`，实际观察 `ModuleNotFoundError`。最初测试参数名误用 pytest 保留的 request，随即更正为 input_path 后执行行为用例。
2. `t03-green-02`：**11 failed / 15 passed**，成功路径因 Windows 真实长路径限制失败；加入内部 extended path 支持后 `t03-green-03`：**26 passed in 4.94s**，无 skip。
3. 追加 snapshot 字段失配、写入失败、同身份并发、既有证据篡改与真实 junction 绕出用例；修正测试重入 guard 后，`t03-review-red-02`：**4 failed / 30 passed**。暴露 declared_version/digest_kind/extraction 被篡改仍恢复，以及磁盘错误未结构化。实现逐字段重建 SourceResource/Snapshot 比对及结构化发布错误后，`t03-review-green-01`：**34 passed in 8.10s**，无 skip。
4. Markdown 审查追加 HTML 未引号 src 和代码/注释示例：`t03-markdown-red-01`：**2 failed / 34 passed**。改为惰性 HTML 属性解析、排除代码/注释后，`t03-markdown-green-01`：**36 passed in 8.06s**，无 skip。
5. 追加五类 `.txt` 正例并禁止 socket 连接、主件在读附件时变动的回归；最终命令及结果如下。

```powershell
.venv/Scripts/python.exe -m pytest skills/common/knowledge/_shared/tests/test_sources_scope.py -q --basetemp=artifacts/test-tmp/t03-final-01
.venv/Scripts/python.exe -m ruff check skills/common/knowledge/_shared/sources.py skills/common/knowledge/_shared/tests/test_sources_scope.py
```

结果：**42 passed in 10.11s**，无 skip；Ruff **All checks passed**。覆盖 E09/E10/E15 的文本捕获/恢复切片，包括原件移走后恢复、原摘要与提取文本分离、UTF-8/BOM/CRLF/中文/空文本、附件独立变更、缺失/未声明附件、零网络、输入只读、sources/control/仓外及真实 junction 拒绝、篡改/缺载荷/失配清单、读取期间变动、同身份幂等并发和失败发布。该机制验证不等同于真实知识语义、人类确认或目标芯片覆盖；候选/确认/stable 事务与端到端验收由本批其他任务完成。

独立审查状态及整批回归由协调任务追加，本记录未冒充独立审查已通过。
