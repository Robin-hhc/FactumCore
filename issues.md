我是 @代码审查，持有 P4 lint_view 节点接力棒。先加载审阅要点参考，再按节点契约执行：先跑固定检查，再独立审阅。

按 Skill 契约，先运行固定检查 knowledge ingest check --json。

机器检查发现 1 个 finding：INVALID_CARD_TAGS（hwdl-frame-flow.md）。先读取卡稿、计划、task 与来源材料，核实问题范围。

机器检查发现 1 个 finding：INVALID_CARD_TAGS（仅报 hwdl-frame-flow.md）。先读取其余 3 张卡稿与卡规范，对比 tags 差异并确认校验规则。

机器检查报 1 个 finding：INVALID_CARD_TAGS（仅 hwdl-frame-flow.md）。先定位检查实现，弄清 tags 的具体规则。

tags 原始字节无重复、非空，为何仅 hwdl-frame-flow 报错？怀疑 YAML 解析将未加引号的数字标签（如 1108、80211）解析为整数。逐一用检查逻辑验证 4 张卡。

确认根因：YAML 未加引号的 80211/8023/1108 被解析为 int。但为何只有 hwdl-frame-flow 报 INVALID_CARD_TAGS，而 hwdl-tx-path/hwdl-rx-path 未报？关键在 lenset: 7 7 与 6 6——注意 frame-flow 卡只有 6 个 tag，其中 80211 与 1108 都变成 int；而 tx-path 卡有 7 个 tag。问题在于 len(set(tags)) != len(tags) 判断：若 int 与 str 碰撞则触发。frame-flow 的 80211(int) 与 '1107c'(str) 不同，1108(int) 与...等等，再仔细看。实际上 check 报错只针对 frame-flow，需看 set 是否因 int/str 混排出现长度差异。先直接验证。

机器只报了 hwdl-frame-flow，但按 cards_v3.py:197-198 的判定逻辑，hwdl-tx-path 与 hwdl-rx-path 的 tags 同样含 int（80211/1108/8023），理应同样触发 INVALID_CARD_TAGS。需确认 check 是否对全部卡都跑了 parse，还是命中首错即停。先重跑完整 check 并确认是否仅报一条。

机器只报 hwdl-frame-flow 一条，但逻辑上 hwdl-tx-path/hwdl-rx-path 同样含 int tag。需查 check 是否对全部卡逐一校验、如何定位卡文件（plan path 是 knowledge/concepts/...，但卡在 .build/cards/），以及为何只报一条。查 CLI 实现。

实际 CLI 在 runtime/ 包（manifest 校验），不在仓内源码。找到 check 校验卡的来源与为何只报一条。

protocol.py 是运行时执行器，cards_v3.py 被当作可执行规则在 runtime/himate_knowledge 外加载（第171行）。查规则加载路径与 check 命令如何收集卡。

cards_v3.py 被 digest-lock 固定，检查规则来自该固定源码。我已用同一 load_yaml 复现：hwdl-tx-path/hwdl-rx-path 的 tags 同样含 int，理应同样报错。需看 check 如何收集候选卡（是否只报首条、或按 plan path 找卡）。读 ingest.py。

_drafts 对 4 张卡都调 parse_card，若任一抛 INVALID_CARD_TAGS，整个 check 在 _drafts 处就被 except 捕获返回单条 finding——但只报了 hwdl-frame-flow。这说明 check 收集卡时对每张卡都 parse，首条异常即整体返回。但为何只报 frame-flow？查 parse_card 中 legacy 判定：concise_only=True 时 not legacy and ... 条件才启用非空/去重校验。看 legacy 计算，frame-flow 与其他卡唯一区别是 tags 数量不同。

关键在 cards_v3.py:191-193：legacy = (bool(set(metadata) - CARD_FIELDS) or (not concise_only and metadata.get("lifecycle")=="draft"))。若 hwdl-frame-flow 之外某卡被判定 legacy，则 tags 校验跳过。但三张 flow 卡字段相同。重新细读报错逻辑——_drafts 用列表推导，首张 parse 失败即抛异常。frame-flow 是排序第一（concepts/flows/hwdl-frame-flow.md < hwdl-tx-path.md），若它先失败则只报它。验证排序与失败卡。

确认：3 张 flow 卡（frame-flow / tx-path / rx-path）都因 tags 含未加引号的数字（80211/1108/8023 被 YAML 解析为 int）而报 INVALID_CARD_TAGS；hwdl-tx-command 通过（tags 全为字母字符串）。CLI 只报首条（按路径排序 hwdl-frame-flow 最先失败）。这是 P3 落位拼写问题 → 应回 P3 materialize_view 修正 tags。

先完整核实其余检查维度（doc_ref 定位、plan 对应、旧卡/来源核对），确认是否仅此一个必要问题，避免遗漏。读取来源材料与卡 spec，核对事实。

规范确认：tags 须为「非空且唯一」的字符串数组。3 张 flow 卡含未加引号数字 tag，被 YAML 解析为 int，违反规范，是明确的落位拼写问题（P3 范畴）。先补做独立审阅的其他核对：doc_ref 定位与来源一致性、plan 对应、事实/依据核对。读取来源材料。

来源结构已核对。现在抽查关键章节内容，核对卡稿的事实与依据（TX 节点、RX 节点、命令），确认除 tags 外是否还有内容问题。

§4 概要设计与卡1 hwdl-frame-flow 高度一致（帧体变换链、07c/08 双路径、22B→42B→22B）。继续核对 TX 详细设计 §5.1 的节点内容与卡2，重点抽查节点7/8/11 的 PID/SNAP/OUI 事实。

TX 节点 1-9 卡稿与来源高度一致（节点2/5/6/7/8/9 的代码片段、OUI 00 17 F2、PID 0x0800、csum_type=0、07c/08 spec 判定均对应）。继续核对节点10/11 与 RX 部分，以及 command 卡。

TX 节点 10/11 卡稿与来源一致（AMSDU 三级链路、PWL 先例、寄存器 H=0x0800AAAA/L=0x030017F2、bit_awdl_snap_en 方案）。继续核对 RX §5.2 与 command §5.3。

RX 节点 1-4 卡稿与来源一致（host/device 侧 PID 转 eth_type、dmac_rx_hwdl_get_data_type 偏移、csum 强制 pass + 802.3 转 eth，代码片段逐行对应）。最后核对 command 卡 §5.3 与 RX 4 阶段调用链 §5.2.1。

command 卡与来源 §5.3 完全一致（命令格式、组帧字段、调用路径、4 处代码落点、前置条件、§6 验证方案标注未执行）。现在补核 RX §5.2.1 的 4 阶段调用链（卡3 的「4 阶段」表述），并确认旧卡/正式库状态（0 卡，全 create 无退役）。

RX 4 阶段调用链与卡3 完全一致（阶段1-4、通路A/B、交汇点 hmac_rx_proc_feature、节点1/2/3 落点）。再确认正式库无旧卡（全部 create 无退役）与 doc_ref 定位一致性，然后形成审阅结论。

正式库确认 0 卡（仅导航 index），files 表 1 行来源登记，全部 create 成立。doc_ref 边界与来源章节一致（§1-4=1-201、§5.1=206-725、§5.2=726-1171、§5.3=1172-1262，边界行为空行/标题，合理）。

审阅结论：

内容事实/依据：4 张卡与来源逐节点核对一致，07c/08 双路径、PID 0x0800、SNAP OUI 00 17 F2、csum 策略、AMSDU 三级链路、RX 4 阶段、command 命令格式/落点均与 §4-5 原文对应；设计/代码片段均标注「设计文档声明」，§6 未执行验证未写成实现事实，依据充分。
决定正确性：正式库 0 卡，全 create、无旧卡退役，符合 P2 决定；plan cards 与卡稿 id/path 一一对应，无 PLAN_CARD_MISMATCH。
唯一必要问题：3 张 flow 卡 tags 含未加引号数字（80211/1108/8023）被 YAML 解析为 int，违反 cards_v3.py 的「非空且唯一 string tags」约束，机器检查 INVALID_CARD_TAGS（CLI 只报按路径排序首条 hwdl-frame-flow，实际 3 张 flow 卡均失败；hwdl-tx-command 通过）。这是落位拼写问题，决定本身正确 → 应回 P3 materialize_view 修正，不需回 P2。
按 Skill 契约（P4 不替作者改稿），走 needs_revision 出口回 P3。先记录审阅结论到 .build/review.md，再交棒。

审阅记录已写入 .build/review.md。现在调用 workflow_handoff 走 needs_revision 出口回 P3。

P4 审阅完成，已交棒回 P3 修订（handoff wh_mvyqet8h_ygqrxype）。

审阅结论：needs_revision（决定正确，稿件需修订落位拼写）

固定检查：ingest check --json 返回 failed，1 条 INVALID_CARD_TAGS。逐卡 parse 定位到根因——3 张 flow 卡（hwdl-frame-flow/hwdl-tx-path/hwdl-rx-path）的 tags 中未加引号的数字（80211/8023/1108）被 YAML 解析为 int，违反 cards_v3.py:195-199「非空且唯一的字符串数组」约束。CLI 只报按路径排序首条，实际 3 卡需一并修；hwdl-tx-command 通过。

独立内容审阅：4 卡 doc_ref 定位与来源章节一一对应（§1-4=1-201、§5.1=206-725、§5.2=726-1171、§5.3=1172-1262）；TX 11 节点、RX 4 阶段、command 命令格式/落点逐项与原文核对一致；设计/代码片段均标注「设计文档声明」，§6 未执行验证未写成实现事实。正式库 0 卡，全 create、无旧卡退役，plan 与卡稿 id/path 对应，决定成立。

唯一必要问题（回 P3 修正）：3 张 flow 卡 tags 数字标签需加引号改为字符串，如 '80211'/'1108'/'8023'。审阅记录见 .build/review.md。

@代码实现 请按上述定位修订 3 张 flow 卡的 tags（加引号确保解析为字符串），修订后回 P4 重新检查与审阅。
