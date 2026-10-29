# FactumCore 知识库系统：待解决问题清单（2026-10-28）

阻塞点逐项清单
① P4→P5 交棒被 runtime 工具问题卡住（已解决）

现象：P4 卡稿生成完、ready 出口条件已满足，但 workflow_handoff 工具在 coder 的 runtime 里不可用，交棒提交不出去；监督者非接力持有者也无权代交。
解决：您拍板"主控手动推进交棒"，之后工具恢复可用，交棒成功。
性质：基础设施/工具暴露问题，非业务问题。
② P3 冻结查询语义错误（当前阻塞的根因）

现象：P7 执行 batch 后返回 phase=needs_revision——内容已发布、索引已构建验证，但冻结查询 hwdl-tx-rx（purpose=implementation）返回空结果，导致激活失败。
根因：查询引擎 match_scope 对 purpose=implementation 只放行 evidence_kind in (implementation, measurement) 的 claim，而这张卡的 claim 是 evidence_kind: design（设计说明书），design claim 永远不可能被 implementation 查询命中。
关键点：friday 仓先例早就踩过这个坑（同源查询首轮 implementation 失败，r2 改成 current 才通过）。thursday 首次入库时 P3 冻结查询直接又用了 implementation，属于重复踩坑。
③ P5 独立审阅未拦截查询语义问题（流程盲区）

现象：P5 审阅对卡稿内容 18 项事实逐项核对全部通过、固定检查全 PASS，但没有检查"冻结查询 purpose 与 claim evidence_kind 的兼容性"——target_queries 不在 P5 固定检查范围内。
性质：审阅范围盲区。如果 P5 就发现，本可以在 P3 重判，不必走到 P7 才发现。
④ P7 终态节点无返工出口（流程设计缺口）

现象：apply_view 只有 completed/recorded 两个出口（都到 __end__），没有返回 plan_change 的路径。遇到"内容已落位但激活失败"的语义问题时，节点内无法自愈，只能流程外返工。
性质：workflow 模板设计缺口。
⑤ 多次 user_cancelled 中断（稳定性因素）

P4 期间有 3 次调用被取消（inv_1793252499676 等），监督者处理您返工决定的调用也被取消（inv_1793261292056）。每次取消都中断了执行流，但不影响已落位产物的完整性。
