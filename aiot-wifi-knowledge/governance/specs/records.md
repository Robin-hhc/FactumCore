# 人工文档确认记录（T06）

ManualReviewRecord 以锁定的 records.schema.json 为字段真源。候选等待状态放在 ChangeSet，不生成 confirmed_by、confirmed_at 或虚假人工记录。贡献者本人可确认，无额外审批人要求；无回复、超时、Agent 名字或普通 JSON 都不是本工具支持的真人动作。

`document confirm --knowledge-root K --operation-id ID --decision accepted --confirmed-by 本人` 展示确切 final-view 文件、固定来源文本和未提取附件限制，再要求人操作终端输入 `accepted <最终视图摘要前12位>`。也支持 confirmed_no_impact、partially_accepted、returned、deferred、deprecated；后四种不授权 apply。非交互输入返回 HUMAN_ACTION_REQUIRED，无记录。无 --yes、自动同意或确认 JSON 导入开关。整条文档分支不调用代码 lint，也不产 LocalCheckRecord/MergeGateRecord。

记录在 logs/document-reviews/<review_id>.json，绑定 operation、确切文件/最终视图、ChangeSet、来源集/快照、范围、相关旧基线、计划与工具/契约。输入在读前和人动作后均复核，旧决定不能覆盖变化后的视图。记录自含摘要会循环，因此 review_digest 保存于外层回执，事务 journal 再固定实际记录字节。

终端 adapter 的身份是贡献者自述；宿主负责保证由真实人操作终端和写记录的权限。TTY/摘要/字段本身不认证自然人，也不防拥有同一文件写权限者伪造记录。本批实际开发验证使用测试专属合成终端；没有为真实业务卡制造确认。聊天中用户回复的可信宿主 adapter 尚未接入，不能宣称已经支持自动将聊天回复转换为确认；在该能力完成前，由用户亲自在其终端执行确认。后续接入须带真实对话动作及宿主凭证，不能仅接受 Agent 自报的 turn ID。

部分接受先记录选择。`document narrow --knowledge-root K --operation-id 原ID --review-ref REF --new-operation-id 新ID --candidate 显式缩窄卡.md` 只允许保留同卡的严格 Claim 子集，保留 Claim 正文/元数据和范围不变，不引入新来源。若需改结论或范围，另建明确修订计划。缩窄后的 exact final-view 必须再展示并得到新真人动作；原部分接受或整包决定不能 apply 新操作。

纯文档确认是语义责任所在，技术校验只防止错对象、陈旧绑定和并发覆盖；不证明代码当前行为、资料权威性或知识检索已可用。模板中的占位身份和时间不能作为完成记录。
