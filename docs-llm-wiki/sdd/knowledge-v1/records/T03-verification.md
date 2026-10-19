# T03 单仓集成验收

日期：2026-10-20。本次沿用用户指定 FactumCore 单仓，把上一批 T01/T02、批准 SDD 与 raw 捕获模块一起纳入主干；无关研究的 dirty 内容只迁移位置，不纳入提交。

## 实测

在根运行 T01/T02 三测试文件、test_sources_scope.py 和 test_document_cli.py：116 passed / 38.79s。固定根快照 `1b42ec81d1b2901e8669524a55caad545d00dfee` 的干净独立 checkout 同一完整集合：116 passed / 39.67s，零跳过；SDD 来源摘要与依赖检查通过。根快照代码摘要与最终提交的对应代码文件保持一致；后续仅添加本记录和状态。

[干净 checkout JUnit](T03-clean-junit.xml) 保存实际结果。覆盖五类 raw、UTF-8/BOM 与原字节/locator、主件和附件变化、缺件、URL/控制文件/越界 junction 拒绝、不联网、持久对象完整性、损坏旧包不覆盖、源移走后恢复、失败发布与幂等。

第一次干净 checkout 发现主设计被 autocrlf 改写，导致来源基线不符；已对两份冻结设计使用 -text 保存原字节，并重新暂存核对磁盘/index SHA。另一次 pytest 未预建 basetemp 的父目录造成测试环境错误；预建 artifacts/test-tmp 后重新完整运行。失败均未算作功能通过。

## 两轴独立审查

Standards：固定 `39904104a0b20c9b19602ccf00f2a26837093be2` 发现下一行 Markdown 引用目的地漏检（P2）。Spec：同快照发现 HTML srcset 附件漏检（P2）。补入三项实际失败回归后修复：下一行引用识别，srcset/imagesrcset 明确返回未支持，object data 与 poster 纳入附件检查。

两位审查者分别对根固定 `e70faf48aeadd5a1f5000df3134fdf56db15d1b1` 复核，均 closed，无已知残留项。Standards 三项固定源码回归通过，Spec 六项独立探针通过。最终 `1b42ec81...` 仅补正设计冻结字节，T03 实现不变。

## 范围与发布

T03 验证限于合成资料和本机 Windows；未导入真实 raw，不证明真实业务覆盖或断电存储持久性。主件仅 UTF-8 Markdown/文本；二进制附件只保留原字节，不宣称提取或 OCR。捕获不改正式知识、来源锁或导航，不访问 source 链接，不调用文档 lint。

本模块按用户授权直接在 FactumCore main 提交并推送，Git commit 是其内容身份；远端 SHA 核对由发布命令实际执行。T05/T06/T07 的开发中代码不包含在本模块提交，后续分别验证发布。
