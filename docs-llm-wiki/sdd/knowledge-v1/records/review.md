# 首批独立审查记录

## 固定输入

- Framework baseline：`8e538be14542f2180b649ed06629fc80902f0850`；初审候选：`ddd94b36916cb30eb427500330f374e37fd3c9d6`。
- WiFi baseline：`9ade7f0313fe3ba829e55f56fce50b053ef659a2`；初审候选：`978a7b02ff768ae249e0d1cf75e1f93d1aa53101`。
- 初审候选通过各仓 `refs/reviews/knowledge-v1/initial` 保留，独立 reviewer 分 Standards/Spec 两轴阅读固定 diff，不用“测试绿了”替代审查。
- 规格来源：固定总体设计及本 SDD requirements、first-slice、T01/T02；当前实现范围之外的模块保持待开发，不当作首批代码缺陷。

## Standards 轴

| 发现 | 实际复现 | 修正与验证 |
|---|---|---|
| ST01：Git status 执行 fsmonitor，违反只读探测 | 在临时仓配置无害 marker 命令，公开 resolve 后文件实际产生 | 每个 Git argv 显式 core.fsmonitor=false，保留真实回归 |
| ST02：独立读取造成摘要 A / 解析 B 错绑 | config A→B→A 返回 B 绑定但携带 A 摘要；Schema 同型问题 | 新增 load_document_bytes，registry/config/lock/schema/CLI 对同一 bytes 解析和摘要，末次复核；公开用例先 red 后 green |
| ST03：修复期间继续发现属性 helper 与子模块递归执行 | clean/process/smudge 和父子 Git fixture 分别证明 marker 可执行 | 安全元数据发现与 status 分离；helper 或子模块条件下跳过 status、dirty=null 并保留原因，仍允许真实入口读取，不伪造 clean |

本机全局可能存在 Git LFS 等 helper；不能靠测试环境屏蔽它们后声称实际探测可用。正常安全 status 场景使用隔离合成配置验证，同时另设外部配置/子模块用例验证 dirty 明确未知及零 helper 执行。

## Spec 轴

| 发现 | 实际复现 | 修正与验证 |
|---|---|---|
| SP01：悬空内部 $ref 抛未捕获异常 | CLI 退出1、traceback，未返回 JSON | 捕获 public Unresolvable，返回 INVALID_SCHEMA_REFERENCE/退出2；公共 CLI 负例已 green，独立 reviewer 复核关闭 |
| SP02：pinned 条件未有快照资格仍返回 match | 合法条件组对不同/缺失 revision 均 match | pinned/revalidate 缺快照证明明确 unknown；不替代后续门禁；独立 reviewer 复核关闭 |
| SP03：入口 junction/链接可读取登记根外正文 | 真实 knowledge 目录 junction 在 resolved/load_context 两模式形成越界入口 | 读取前和末次复核核对各入口真实路径所属根，拒绝 ENTRY_PATH_ESCAPE；保留 Windows 实际联接回归 |

## 验收口径

以上是本地机制审查和合成复现；不证明 hostile OS 并发进程已隔离、实际业务已覆盖或宿主必触发。最终回归命令、测试数量及候选载荷摘要记在 first-batch-verification.json。未修复或未验证的发现不能用摘要计数关闭；最终补丁由 reviewer 再核对。


## 最终复核结果

最终补丁候选 `9d42b0fec8638b2c269f468afc900c40a8b87005` 已独立复核：Standards 原 P1/P2 及关联修正可关闭，相关14项回归通过；Spec SP01/SP02/SP03 均可关闭，未发现本次修补引入的直接回归。最终整套 **69 passed、0 failed、0 skipped**，Ruff check/format、compileall、SDD 追踪检查通过。

WiFi 声明契约已在本地提交 `898ece0a3a1721a77910aed3518e0fa189f50860`；从该提交全新 clone 后四类契约入口再次验证默认 workspace 成功，六业务 Target 仍明确未知，不把 checkout/Schema 成功当作业务接入。
