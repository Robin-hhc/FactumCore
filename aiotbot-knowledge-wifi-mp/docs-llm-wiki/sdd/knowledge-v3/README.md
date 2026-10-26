# 知识库设计对齐与实现

本轮以用户确认的[详细设计快照](baseline/知识库详细设计.md)为唯一规格基线，原文 SHA-256 为 `32df6c9505f3f7c6e8220f90a02a030641d5c9f39d0402ac80154b6556ad2f54`。本目录记录实现筛查、任务、测试与验收；不向面向读者的设计文档写入开发进度。

后续用户明确的[本地 ingest 与人工上库边界](local-ingest-boundary.md)补充上述原始基线，并已反映到现行详细设计。原快照与原验收记录保留，不将人工提交、CI 或合入继续作为 ingest 完成条件。

代码内容复核随后按用户决定改为[独立 Agent 复核记录与固定脚本校验](agent-content-review.md)，取消代码复核的公钥登记和密码学签名门槛；真人确认与共享发布回执规则保持各自边界。历史试验中的签名接入停点不再作为现行代码入库前置。

```mermaid
flowchart LR
    B[冻结设计和现状] --> A[全量实现筛查]
    A --> D[差异与任务]
    D --> R[公开接口失败用例]
    R --> I[分组实施与验证]
    I --> V[集成回归与独立复核]
    V --> E[验收事实和外部待办]
```

入口：[需求与差异](requirements.md)、[实现设计](design.md)、[修改落点](changes.md)、[任务](tasks.md)、[测试计划](test-plan.md)、[本地验收](acceptance.md)、[基线身份](baseline.json)。`records/implementation-before.json` 保存修改前实现指纹；`records/history-before.json` 保存历史工件指纹，v1/v2 不重写。

本轮不增加此前暂缓的新 search 索引过期检查，不更换 Workflow 引擎，不机械合并节点 Skill，不接入虚构业务代码、Target 或真人确认。本地合成验证与真实宿主、真人、六 Target、远端 CI 和权限验收分别报告。

后续真实语料验证见[真实 WiFi 试验](real-corpus-trial.md)：旧代码原字节导出、公开协议、草稿检索与独立源码核对，以及实际发现的兼容性修复。它与上面的冻结实现验收分别记录。

真实卡的后续自然问句、范围过滤、同版读取及已知查询开销见[检索试查](retrieval-probe.md)；多卡覆盖与性能调整另按后续试验结果判断。

扩展到 14 张候选、44 道冻结问题及 20 个治理探针的结果与统一调整方案见[扩展真实语料验证](expanded-corpus-trial.md)。实现基线保持 `3d853a9`，本文档与证据不表示优化已经实施。

按“背景知识与具体索引、Agent 回源确认、准确率优先”的后续要求，拟采用[查询调整设计](background-retrieval-design.md)。该页列出主详细设计待确认的同步范围；扩展试验中的卡内答全率及 5 秒／32 KiB 建议不作为本次验收门槛。当前仅先补查询 Skill 的回源指引，正文返回及来源批次优化尚未实施。

后续目录调整按用户确认的[配套能力迁至项目根](capability-root-layout.md)执行：根 AGENTS/config 与 skills/workflows 同级，知识根继续保存原件、知识和治理。历史快照、记录及旧路径保持原字节；查询正文与来源复用优化仍待确认。

Windows／Linux 已有 Python 3.11 时的依赖准备入口、版本选择与安装验证见[运行依赖安装](runtime-installation.md)。它复用已有 catalog 安装器，内部 Agent 仍由部署方手动接入。

用户随后确认的[多仓工作区与模块映射](workspace-mapping.md)将人工配置收敛为 `code_root` 与模块相对路径、芯片、端、特性和用途；运行时只读取文件并固定内容指纹，不探测或执行 Git／mm／manifest。该设计补充原始规格，历史配置、快照及记录保持原字节。
