# T06 人工确认与部分接受验收

日期：2026-10-20。T05 已发布 FactumCore main `7a0a34af2e2ad68b58c6b8e8d16cc1080378916d`，远端 SHA 实际核对一致。

## 实现范围

`document confirm` 提供由真实人操作的交互终端 adapter；展示固定来源和确切最终字节后要求决定与摘要 challenge。贡献者可本人确认，不增审批人。非 TTY、无回复、错误 challenge、Agent 姓名参数不会生成记录。无 --yes 或普通 JSON 导入批准通道。聊天回复的可信宿主 adapter 尚未接入，不能声称已支持该方式。终端身份为自述，终端/文件写权限由外部宿主管理，不把 TTY 或摘要当作身份认证/ACL。

人工记录固定 operation、ChangeSet、final-view、文件、来源、scope、相关旧基线及工具/契约指纹。awaiting_confirmation 只保存在候选中，不预填人或时间。accepted/confirmed_no_impact 覆盖完整最终视图；returned/deferred/deprecated/partially_accepted 不授权 apply。

`document narrow` 由显式缩窄卡保留同一 Card 的严格 Claim 子集、原断言和范围，不引入新来源；生成新 operation 与最终视图后必须新的人动作。其他结论修订另起明确计划。实现分解为 changes.py 公共入口与 confirmations.py 内部 adapter，K/contracts/records.py 只委托共享实现，不造第二套规则。文档链无代码 lint。

## 实测与两轴审查

初始 8 项失败：confirm/validate_review 尚未实现，CLI 尚无 confirm；随后 10 项绿色（含部分接受重确认、等待、本人确认及修改中断）。Spec 独立审查固定 `617604194d30062cb630644ab58d3f49d3778a9f` 复现展示时临时变更后还原仍 accepted、相关基线变化仍返回 accepted；两轴均复现完整 Claim 逆序选择导致自身记录不可消费。

三项回归实际见 **3 failed** 后修复：显示时核同份 data 摘要、验证记录重核当前 baseline、将 Claim 选择规范到视图顺序。针对集合 **13 passed / 46.52s**。两轴独立复核固定 `bbcca08d44ef36e2ac9b1f79f346605de8fcc9b0`，全部 closed。

该快照干净 checkout **181 passed / 105.47s，零跳过**，SDD 与 Ruff 通过；[JUnit](T06-clean-junit.xml) 保存实际结果。此前初版干净快照 178 项通过未包含三项审查回归，故以本次 181 项为本票完成证据。Standards 审查首次另有一次 raw setup 写入失败，改用独立短临时路径复跑 10 项通过，没有当作确认模块通过依据。

全部人动作用例均是测试专属合成终端，没有真实业务确认或真实 stable 卡。顺带清理 T05 空模板/导航末尾空行，使 scoped diff-check 通过，不改变领域事实。按授权单独在 main 提交推送；事务落位、完整恢复和检索各按后续任务验证。
