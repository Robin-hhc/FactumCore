# WiFi 知识入库 Workflow

OpenFlow 编排已安装的九个配套 Skill，恰好七节点：P1扫描 → P2备料 → P3作者决定 → P4完整稿 → P5独立审阅和完整检查 → P6待发布记录 → P7发布及收尾。P5由reviewer执行，其余由coder执行；角色隔离由宿主落实。

新Workflow使用新operation。普通P1只对照当前输入、正式处理记录和维护限制，出口仅 `scanned`（进入P2）与 `unchanged`（结束）；不枚举旧draft、journal或索引收尾。兼容的两种finalization数组为空，execution_history为not_inspected。无变化仍可按用户明确修订目标进入P2，不回溯上次未记录的作者意图。

P1—P6本批业务新文件，包括原件／附件副本、提取定位、旧卡、代码／构建／运行材料、事件拟稿及输出，均写本批 `.build/operations/<op>/`；正式卡、导航、来源锁、事件、证据和活动索引不变。P4/P5冻结stage→final路径和完整字节；P7不改写已审内容。P5缺料回P2、判断错回P3、稿件错回P4，使用新op和明确前序引用，保留原scan身份，不覆盖旧工件。

P7保留输入、锁、CAS、备份、实际回读和未完事务保护。内容及必要正式证据发布并核验后，才保存正式成功处理记录；然后完成适用索引全验、冻结查询、同代read和原expected_active激活。仅记录批保留欠账，不建索引。全部适用收尾后清本批明确拥有且可删的stage，正式manifest/completion位于 `logs/publications/<op>/`。cleanup_pending保持已发布事实，batch_complete仍为false；重入仅补缺失阶段或清理，不重复apply。借用、保护或用途不明项保留并说明，最终小响应可仍在.build。

已知当前P7中断可按明确op和原引用续办；旧事务按配套版本显式恢复。P1不承担旧历史发现。罕见P7半写自动修复、全目录原子切换和孤儿stage周期GC不在本轮保证内。清后普通scan/lint/query/read及结果、提交核对不依赖生产者旧view；缺本机索引时显式重建。

`workflow.yaml`定义节点、提示和分支，`layouts.yaml`保留七节点画布位置。Git提交、CI、合入、真实宿主取消和权限隔离分别按实际证据说明。
