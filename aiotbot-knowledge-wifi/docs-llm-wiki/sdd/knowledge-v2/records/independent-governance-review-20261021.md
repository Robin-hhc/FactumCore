# 节点实现独立审查交接

日期：2026-10-21。审查范围为18节点实现中的治理、来源、发现、安装、检索与索引公开边界。此记录保留发现和交接依据，不替代任务状态、最终验收报告或发布SHA。测试中的签名、代码仓、构建记录均为显式隔离合成输入；未读取受限gold。

## 治理节点已关闭的反例

治理独立工作分支提交`9b79915`后，7包共43项测试通过，7包Skill静态校验与Ruff通过。实际主仓合入身份以最终发布记录为准。

| 发现 | 修复与回归证据 | 边界 |
|---|---|---|
| 中断A事务后可开始B事务正式写入 | 全域非终态journal阻断新事务；已committed重入保持只读 | 合作写者OS锁；不声称普通文件系统是ACL |
| rollback可能删除未尝试目标上外部创建的相同字节文件 | 写前持久attempted；回滚只恢复本事务已尝试项并保护新编辑 | 现场冲突保留，不强行覆盖 |
| immutable记录半写后可能卡住恢复 | fsync临时文件后create-if-absent原子发布 | 多文件事务仍依靠journal恢复 |
| 域契约或本包有效pyc可能绕过源码摘要 | 验过的域源码内存compile；CLI新随机cacheprefix并禁写bytecode | 不使用`-B`单独作为阻读缓存保证 |
| 正式探索回执`context_loaded`及`.build/project-context/`被旧fixture状态假设拒绝 | 兼容正式状态和路径，仍要求完整Target/build/config与签名 | 发现回执中的unknown不能变成正向代码证明 |
| 代码身份仅比较待审字段，未核实际Git根/origin；partial clone可能隐式取网 | 核实际top-level/origin，禁lazy fetch和传输协议 | 缺本地对象为incomplete，不自动修复 |
| 代码apply中断后HEAD变化会同时阻断resume与rollback | resume保留current校验；rollback验历史签名、确切视图、原件和备份 | 不把历史资格用于新apply或current消费 |
| 显式空/部分Workflow参数可绕过前验或在副作用后报错 | 参数出现即校验完整run/node/attempt，非法输入先于handler拒绝 | Workflow文件或退出0不等于真实人同意 |

## 跨模块发现与交接

以下内容是审查观察时的可复现问题，已分别交给实现者；闭合结论须对应后续修改和回归，不能仅凭此表宣称仍存在或已通过。

后续只读复核：检索刷新实际摘要CAS、从固定发布commit读取来源锁逐卡验证、退役卡以historical_files判资格这三处修复已检查；独立运行query/index两份`tests/test_qualification.py`，15项通过。完整公开CLI纵向验收由最终runner另行记录，不以这15项定向测试替代。Workflow前验和完整来源附件展示由主集成者补齐后同样需纳入最终回归。

| 级别 | 触发与影响 | 交接要求 |
|---|---|---|
| P2 | 回归节点先activate后校验不完整Workflow元数据，可能已改active而返回error且缺manifest | 所有包装器前置校验显式Workflow；与治理包同协议 |
| P2 | 人工展示仅解析卡选定的source_refs，可能漏显捕获包附件及全包提取缺口 | 通过公开来源接口展示固定附件原件引用/hash与不解释声明，将缺口同包绑定签名 |
| P2 | 最后source刷新只核immutable snapshot，代码正证明的boolean豁免可能接受核验后又变化的当前代码 | 比较刷新前后实际当前代码摘要，变化要求重试，不撤销原证据与最新检查快照分离 |
| P2 | shared复验拿当前整份sources.lock与旧发布commit比较，无关追加来源也使旧卡current/historical失效 | 固定发布时锁身份或核提交中的相关来源子集，当前资格继续逐卡/逐Claim验证 |
| P2 | shared发布要求deprecated代码卡出现在current eligible_files，而合法退役卡只具有historical_files | 退役卡按历史资格持久保留，stable代码卡仍需最新正向merge证明 |

来源新增代码捕获及维护路径另交叉核查过：代码`bytes`定位在最新实现中已受范围校验并明确不作语义解释；早期基于未导入版本的selector疑问已撤回。实际root/origin变化后的current_source_matches由来源实现者补回归；不可变历史恢复应继续可用。

最终闭合：完整19组运行199用例（198通过、1个Windows符号链接用例跳过）。后续独立审查再用公开CLI复现“receipt精读c1仍返回c2来源原文”的P2；新增失败测试后，按最终Claim集合收窄sources/gaps，完整查询包15项通过，审查者只读确认修复。未重复累加旧查询用例，最终唯一用例为200项，199通过、1跳过。实际身份与各组证据摘要见开发验收和实现manifest。

## 尚需真实外部验收

真实宿主展示及人动作适配器、全局Skill新会话隐式选用、六个真实Target及三pair构建、真实CI/committer发布、跨组权限与凭据隔离均不由上述合成测试关闭。最后任务状态和验收层级由最终验收记录单独确认。
