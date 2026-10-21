# 2.0 运行记录与真人确认

所有机器记录使用 schema_version 2.0、准确 record_kind 和规范对象摘要。节点记录绑定 operation、规则摘要、实际 Skill 包及运行依赖身份。摘要只检测内容和绑定变化，不认证人，不提供权限。

纯文档的 confirmation-prepare 生成 exact final-view 全部拟写文件、来源说明、限制及新 challenge 的展示包。Workflow 的 user Gate 等待真实人操作；confirmation-record 只接受安装清单中受信宿主适配器签名的原始事件，检查 public key、actor_type、decision、challenge、display/view 摘要、时效和旧操作状态。未接入可信适配器时保持 awaiting，不能退回自填 confirmed_by、TTY 或普通 JSON 自动认可。

贡献者本人可以确认，不额外要求第二审批人。无回复、超时、Agent 自报、退回、暂缓和部分接受均不放行。部分接受经 revise 生成新 operation、精确 view 和新展示后重新确认。文档分支不调用 local-check/merge-check。

ManualReview 持久保存原签名事件及 exact-view 绑定，apply 时再次验证宿主签名与当前输入，不能仅相信可重新计算的记录摘要。生产包不包含签名私钥。合成适配器只对受信安装清单明确指定、含专用隔离标记的测试根有效，相关记录必须声明 synthetic，不能当作真实人验收。

代码卡使用受信语义审查证据和逐 Claim 正支持生成 LocalCheck；MergeCheck 按最新获授权业务快照只读复验。缺路径、Target、宏、构建、固定版本或正支持证据返回 incomplete；零 finding 不等于通过。apply 通过受信 local-check 公开 verify-proof 入口复核证据，不接受任意自报 passed。

事务 journal 记录完整 writes/deletes、expected-old/最终摘要、持久备份及每步结果。committed 重入返回原结果；非终态先受控恢复。发生外部新编辑时停止并保留现场，不覆盖编辑来“完成恢复”。索引和维护记录独立绑定代次、当前事件 epoch 及两水位，索引回滚不能撤销当前阻断。

真实宿主动作桥接、自动触发、六 Target、CI 合入与权限部署各有独立验收；Schema、包测试或合成签名不能代替。
