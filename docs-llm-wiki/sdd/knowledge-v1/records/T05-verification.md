# T05 候选与最终视图验收

日期：2026-10-20。T03 已发布于 FactumCore main `e88bbc333d2027cc137c94d50d085cc3ee3d936e`，远端 refs/heads/main 实际核对一致。

## 实现和范围

七类 Profile 的显式 Markdown 由作者提供，cards.py 解析固定 Card/Claim ID、来源映射、条件引用及正文锚/行段；不机械摘录原文制造结论，不以结构通过证明语义。七模板与导航按原设计展开，glossary 对应 knowledge/glossaries。

`ingest plan` 记录 create/update/merge/split/deprecate/defer/no_change、理由和相关卡；`ingest materialize` 仅对单卡 create/update 生成 candidates、确切 stable final-view、来源锁增量、导航与人工差异包。复杂跨卡计划尚不可 apply，留在 T09。规划/物化不改正式资产；每个拟写 Claim 都须绑定来源，且候选须关联本次捕获，否则返回 EVIDENCE_REQUIRED，作者应 defer。

同 operation 整目录暂存后不可覆盖发布，重复相同请求幂等，不同请求明确冲突。导航编码文件名并用稳定 ID 摘要标记；同 source_id 的 raw 版本目录可迁移当前定位，旧 snapshot 的字节、retrieval 与 recovery 留存。

## Red / green 和审查

卡解析初始缺失 cards 模块，候选初始缺失 changes 模块，均有实际 red。解析模块另补隐藏 HTML 注释假锚/假章节 red→green。第一次 cards + changes 联调 46 passed；加入 CLI 与篡改例后 48 passed。

独立 Standards 审查固定 `b1a01e648ed9958ae85d56267f62249f53fd2688`，发现同 operation 并发改用途、空格文件名导航错误两项 P2。Spec 轴发现跨版本路径阻断更新、空 Claim 来源仍生成 stable view 两项 P2。前三项在主执行器补回归实际见 3 failed；空来源由独立审查者复现。修复后针对集合 **52 passed / 20.53s**。

两轴分别复核固定 `5bb77f760784b98c00bbdcbccb92ec432518a0b8`，全部 closed；Standards 2 项、Spec 5 项独立验证通过。该快照干净 checkout 全量 **168 passed / 61.70s，零跳过**，SDD 与 Ruff 均通过。[JUnit](T05-clean-junit.xml) 保存实测结果。此快照不包含并发开发的 T06/T07；本次提交代码来自该快照的暂存对象。

## 交付限制

全为合成输入，未生产真实 stable 卡，未执行真实人确认或业务实验。不同结论的 ID 延续仍由作者明确判断，工具不猜语义相似性。结构与来源绑定检查防止写错对象，不替代人工文档确认。按用户授权单独提交并推送 main，后续票记录实际发布身份。
