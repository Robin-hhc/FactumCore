# 测试计划与证据层级

先写反映外部行为的失败测试，再实现、针对回归、独立审查。优先调用公开CLI，用隔离K复制件和受信测试catalog；pytest临时路径必须K/artifacts/test-tmp/<本次末级>。不读受限gold、不操作真实知识或main，不用mock返回pass替代真实模块行为。

| 层级 | 执行内容 | 能证明什么 | 不能代替什么 |
|---|---|---|---|
| S0 规划静态 | 文件/链接/Skill数/票据DAG/源hash/v1字节 | 文档与追踪结构一致 | 产品CLI、语义或部署已用 |
| S1 单节点 | 每包tests/test*.py与依赖锁、成功/阻断/篡改/输入不变 | 节点公开行为与安全拒绝 | 完整链路或真实人 |
| S2 合成单仓跨节点 | 五raw toy、代码toy、fixture限定认证人事件、事务故障、索引/维护与18包调用 | 机制与接口闭环 | 真实资料正确/宿主触发/六Target |
| S3 包与Workflow | 固定loader/catalog/角色、2模板可达/产物/停等/重入 | 包结构与受控运行 | 真实UI人动作/隐式发现 |
| S4 真实外部 | T211独立环境/身份/工程/CI/访问撤销 | 明确实际执行的对应层级 | 没跑的其他环境或ACL主张 |

| 验收 | 需求 | 主票 | 必须验证的行为/反例 |
|---|---|---|---|
| E201 | R201 | T201 | 只WiFi、main不虚造源码、领域规则与节点程序职责分层。 |
| E202 | R202 | T201 | 产品2.0、七Profile、来源/记录/范围单点契约，锁定代码与声明摘要。 |
| E203 | R203 | T202 | catalog解析精确包/解释器/锁，不自动安装，不发布本机路径。 |
| E204 | R204 | T202 | resolved/context_loaded分开，歧义/旧登记/换仓失效，无整盘扫描。 |
| E205 | R205 | T203 | 只五raw、固定字节/locator/恢复，来源网页/映射延期，原件只读。 |
| E206 | R206 | T208 | Git/dirty/导出固定实际字节，真实构建宏/Target未知保持unknown，受控只读Git。 |
| E207 | R207 | T204 | 七Profile、六决策、逐候选唯一处置，merge/split/deprecate保留替代导航。 |
| E208 | R208 | T204 | 精确writes/deletes含导航与来源锁，stable字节提前固定；生产不写正式资产。 |
| E209 | R209 | T205 | 可信adapter签名人事件；无动作/Agent/陈旧/部分接受不apply；文档免代码lint。 |
| E210 | R210 | T205 | 域锁/全写集CAS/持久备份journal/幂等/恢复，单文件原子而非虚称多文件原子。 |
| E211 | R211 | T208 | 正向逐Claim证据，local/最新授权merge只读；缺代码/证据incomplete，纯文档拒绝门禁。 |
| E212 | R212 | T206 | 全候选先资格过滤，仅有效Claim重计分求全局topK；metadata同样受资格约束。 |
| E213 | R213 | T206 | 同代read/receipt、唯一snapshot/locator、local/shared资格、真实merged身份。 |
| E214 | R214 | T207 | 幂等事件/条件化影响、live block、双水位、受控复核恢复。 |
| E215 | R215 | T209 | 18Skill/2Workflow、user Gate、不可变run/node/attempt manifest、模板可达与公开CLI复用。 |
| E216 | R216 | T210 | 单包/单仓跨节点/真实人/宿主/六Target/权限/CI分层，缺外部输入保持pending。 |
| E217 | R217 | T210 | 有用户授权的外部发布流程执行Git；节点只交接，单仓跨节点分别记录实际SHA/远端/包身份。 |
| E218 | R218 | T201 | 统一JSON协议、精确tool/rules摘要、status/phase、0/2/3语义和安全路径。 |

四项持续回归：metadata资格与Claim一致；过滤后重算全局topK（错误高分/阻断降分反例）；完整批次逐候选终态（含零落位）；受控Git禁止外部执行且输入不变。另需陈旧确认/新source snapshot、真假人事件、崩溃并发恢复、candidate evaluation与shared真实身份、输出前live block反例。

每票先记录red，再记录针对测试/回归/审查与实际发布身份；没有真实动作或外部条件时，写not_run/pending与缺口，不能填pass。所有测试报告保存实际命令/代码与规则包摘要、fixture边界和结果。T211只有真实人、真实宿主、六Target/三pair、真实CI合入、权限撤销分别留证后才结案。


## T211真实外部验收（独立于合成机制）

| 验收 | 需求 | 真实证据要求 |
|---|---|---|
| E219 | R209 | 真实人确认完整视图；无动作/Agent/未签名不通过，视图变更重新确认 |
| E220 | R204 | 真实目标宿主从仓外只给代码路径，实际可见/选用/加载工具轨迹成立 |
| E221 | R206 | 真实chip12/chip08/chip07c六Target/三pair逐槽登记并分读取/构建/运行层留证 |
| E222 | R213 | 实际受信CI/committer合入与shared内容/证明身份一致，无伪merged或静默local降级 |
| E223 | R216 | 真实跨组访问拒绝、存储/会话/端点隔离和撤销负测；目录/filter不作ACL证据 |
| E224 | R217 | 当前FactumCore远端实际发布与本地提交一致，节点包摘要和规则身份可验证 |
