# WiFi 知识治理巡检

用于个人本地及外部半日／每日调度：自动发现 raw 未入库变化、直接登记的代码文件变化与旧欠账，并复用 ingest 能力处理。公开 Skill 仍为八个；同名 lint Skill 继续提供独立只读检查及 P5 review。

1. `sync_workspace` 调用已安装 maintain 的 `patrol-sync`。配置来自控制端的 `sync.argv/cwd/timeout_seconds`；未配置同步时为 skipped，仅检查本地现状。内部可适配根目录 `git mm sync`，其它 MM 子命令不作假设。
2. `plan_patrol` **另起 CLI 进程**，重新加载实际规则／配置／知识仓，调用 `patrol-plan`。脚本比较上次成功水位与各仓 HEAD，合并未提交修改，再只对命中登记文件核 hash／符号；首轮或缺历史等情况回退全部登记文件精确核对。读取实际 `plan_ref/report_ref/source_request/counts/gaps`。
3. 有内容事项时，`prepare_sources` 直接用 `source_request` 调用 source.prepare。请求明确取“变化 raw + 待修旧卡对应 raw”的并集，纯代码可使用空 raw 加明确 targets。逐单元坏材料保留 gap，漂移仍阻断。
4. 复用 ingest 的 P3、P4、独立 reviewer P5、P6、P7；算法和返工边相同，仅 P7 完成后回 `complete_patrol`。不嵌套 Workflow，也不复制 Python 内容生产算法。
5. 仅索引事项走 `refresh_index`，复用公共索引、实际查询和同代 read、原 expected_active 激活。
6. `complete_patrol` 消费原 `plan_ref` 及真实发布／completion，重新核来源、正式跨轮 Claim 欠账、候选元数据引用和活动索引。事项已完成而仅缺失／陈旧派生索引时，复用实际构建、查询和激活补齐；实际完成才 CAS 保存本地成功基线。欠账、失败、漂移或 cleanup 未完返回 pending，基线不推进。无待办也经此确认后结束。

current 的整文件证据改变需交作者复核，即使只是函数前插行；guidance 的 code_ref 仍唯一可定位时使用当前位置，不重写旧 locator；historical 保留可恢复的旧依据。删除、改名、歧义及不可解析分别报告，不猜测替换入口。未登记的间接语义依赖暂不扫描。

已发布未完成 P7 时，plan 返回 blocked 及精确 operation/publication/completion/resume_request。按该引用续办原 batch 的缺失阶段，不能新起 apply 重放。基础配置／登记损坏也保留实际阻断；没有有效结果的运行故障留在原节点等待。

实现位于已安装 maintain 和受锁公共 contracts，Workflow 只分发 YAML、布局和本文。原独立 ingest 不变。观察日志／库存位于本机 `K/logs/patrol/<操作>/`，成功水位位于 `K/.build/runtime/patrol-state.json`，均忽略于 Git；P7 不删除完成核验所需的巡检观察。旧证据、旧定位及正式历史不覆盖。Git 提交、推送和 CI 合入保持后续独立操作。

外部调度前需在内部验收实际 MM 配置、同步覆盖仓、权限、宿主新进程规则重载及 reviewer 隔离。这里的脚本和合成测试不证明真实 OpenFlow 调度或业务知识准确性。详细流程、分支和接口见领域[详细设计 §3.1](../../../../himate/himate-knowledge-wifi-mp/docs-llm-wiki/知识库详细设计.md#31-lint-的检查流程)；安装后从实际知识根文档读取。

节点在实际执行端调用知识根 `python K/knowledge.py <阶段> --action <动作>`；巡检同步使用 `patrol sync`，后续 `patrol plan` 必须新起 CLI 进程重新加载同步后的运行实现与规则。Skill 只提供指令与文本契约，不携带脚本。CLI不调用模型，作者判断与P5独立reviewer仍由宿主安排。
