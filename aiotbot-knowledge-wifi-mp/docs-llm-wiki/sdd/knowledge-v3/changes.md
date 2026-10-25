# 修改点与代码落点

完整筛查先记录于 [requirements.md](requirements.md) 和 `records/audit-*.md`；两份交叉复核报告补充公开反例与关闭依据。批准设计未因实现便利而调整。

| 需求 | 实际修改 |
|---|---|
| R301 | E0 保留独立发现；ingest 以扫描开始。能力仍在领域根，catalog 提供三个主命令及维护分派 |
| R302 | source-scan 的 scan/status：默认五类 raw、完整性、增删改/未完成/读失败、正式记录谱系及本机停点；pending 记录不证明完成 |
| R303 | prepare：全状态来源反查、主题候选与 requires/derived_from 扩展；逐卡实际采用旧版的不可变材料、定位和差异；接入实际授权的新代码 bundle |
| R304 | plan/review：先封存逐 Claim 决策再产稿，融合来源、单写者、保留范围、目标问题、风险抽样及未抽范围；M-only 不造 raw 单元 |
| R305 | mixed 分区取得真人与代码证明，缺一拒绝；preserve 不得删改或漏掉旧 Claim；确认对象、来源、规则或基线变化须重核 |
| R306 | checks 与只读 lint：原生 CheckReport/0、1、2，完整合成视图、格式/Profile/锚点/关系/来源/临时全索引；P7 实际重跑，不只信报告摘要 |
| R307 | records：自包含扫描清单，逐单元/维护 Claim 覆盖、观测与采用版本、缺读不准完成、真实 apply 补记和结构化进度兼容 |
| R308 | 原 CAS/锁/备份/journal 纳入受控记录；仅记录批不夹带卡稿；全索引与本批 query/read 后精确提交；verify-submission 核实际 Git 对象及写删清单 |
| R309 | indexing 共用 SQLite 构建/完整核验/同代正文，Schema 3.0、分词 2.0；资格先于 topK；M 比较真实上下文；共享资格核受信签名、同提交摘要及逐引用来源谱系 |
| R310 | 固定可信 check.py/check.sh 把候选当数据，复用纯检查；空库已有坏来源锁仍拒绝，历史引用不误套当前代码门禁 |
| R311 | 20 个 Skill、24 份上游原生产物合同、单一 ingest Workflow；复用能力按 node_ids 分合同；更新当前入口，保留 v1/v2 原字节 |

Windows 长路径读写在能力边界统一修复。原硬退出测试仍在真实 OS 替换后退出，验证事务屏障、外部修改保留及精确恢复；没有缩短路径掩盖问题。

补充跨机接口复核关闭了三个缺口：已提交代码由实际 capture-code 自动登记可严格恢复的 Git 版本；仅记录批可关联未修改的正式卡／Claim；共享 pending/维护负事实可在没有旧机器 events 时重建。后继只对同 Claim 明确复核才解除限制，原件 partial 不直接封掉已验部分。固定 lint/CI 还须读取真实当前或历史卡正文核对记录引用，不能靠一个无法从 JSON 调用的 callback 占位。

本轮仍不增加新 search 索引时效检查，不更换 Workflow 引擎，不机械合并 Skill，不提供虚构业务映射、宿主注册、真人签发或远端 CI 配置。
