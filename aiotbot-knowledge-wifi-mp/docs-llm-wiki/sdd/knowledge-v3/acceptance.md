# 本地实现验收

已按冻结设计完成实现筛查、修改、公开反例修复和交叉复核。本地合成机制验收通过；真实业务与宿主接入验收单列待办。

| 项目 | 实际结果 |
|---|---|
| 设计基线 | 原文与快照均为 `32df6c9505f3f7c6e8220f90a02a030641d5c9f39d0402ac80154b6556ad2f54`，829 行，70569 字节，未改动 |
| 历史保护 | 123 份 v1/v2 工件逐文件核对，0 差异 |
| 当前实现身份 | [330 份实现文件指纹](records/implementation-after.json)，规则锁 `b3ffb8a84e3009dd4cb87fdba7fe3c9a9ab9886fdf9c0172caf87a0ed73f3873` |
| 验证范围 | 20 个 Skill 测试组及领域/集成组；290 个独立用例，289 passed、1 skipped、0 failures/errors |
| 跳过原因 | 当前 Windows 账号不可创建普通符号链接；junction/越界拒绝另有通过用例 |
| 静态检查 | 全部当前 contracts、Skill、evals 和 check.py 的 Ruff 通过 |
| 编排兼容 | 真实固定 OpenFlow `1901a463efca222542a4634d7ce50c7b244b2bab` loader 装载 20 Skills / 24 原生产物合同 / 1 Workflow；Git Bash 包装入口通过 |
| 当前工作树 | 未创建 FactumCore 提交或推送；Git HEAD 与任务开始时相同，既有未提交工作保留 |

结果与输入身份见 [verification.json](records/verification.json)、[综合结果](records/verified-suite-summary.json)、[设计/历史保护](records/preservation.json)、[修改清单](changes.md)和[实现差异指纹](records/implementation-delta.json)。

验证采用完整 21 组回归加一个测试设施的定向纠正复验：原 full03 的 289 项中，业务断言通过后有一项 Windows 长路径目录清理失败；仅修 fixture 的原生路径清理，再以更长路径重跑整个 local-check 组，16 项通过，包含原 15 项及新增清理逃逸拒绝。综合结果以该组替换原组，不把重复执行累加。原[完整结果](records/v3-final-20261025-03.json)、[纠正复验 stdout](records/localcheck-native.stdout.txt)和[JUnit](records/localcheck-native.xml)保留，原失败未改写。

已实际覆盖的核心链路包括：

- 自动全扫/增量/缺失/未完成与逐卡实际旧版材料；明确依赖扩展及 M-only 代码变更。
- 逐 Claim 计划、preserve 保护、实质 skip 风险复核、混合稿两类真实 fixture 签名及缺一拒绝。
- 完整视图只读 lint、历史卡引用的 JSON/Git 正文恢复、虚构引用/坏 hash/缺正文拒绝；固定 CI 不导入候选程序。
- 卡与处理记录同一 CAS/journal，真实进程硬退出、外部修改保留、恢复与仅记录批。
- 已提交代码经实际 capture-code 自动 Git 恢复、代码核验、native lint、严格 P7、实际索引和本批目标 query/read。
- 共享接纳凭据与逐引用来源谱系；删除旧机器私有状态后，正式 defer/pending 仍阻断相应当前用途，后继同 Claim 复核才能解除。
- 索引全量集合/行值/版本/分词/正文核验、资格先于 topK、检索与读取同代、收尾通过后精确 Git 提交验证。

真实宿主命令注册/隐式选用/Workflow 全程运行、真实人适配器和 Agent 提炼质量、真实六 Target/三 pair、受保护远端 CI/合入以及跨组权限均未由这些合成结果证明，继续保持待验收。源码根、构建、版本等真实信息未提供时保留 unknown。

新 P7 当前要求确切 Git 原版可恢复；本机对象或 dirty 来源没有受支持的持久恢复条件时明确阻断。历史本机 fallback 不冒充可跨机依据。新 search 索引时效检查仍按用户要求暂缓；未更换 Workflow 引擎、未机械合并 Skill。
