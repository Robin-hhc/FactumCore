# CANN 软件栈源码仓核验与 AIoTBot 对应关系

日期：2026-09-30。范围：用户列出的 27 个 `gitcode.com/cann/<repo>` 仓，结合此前已实际安装的 CANNBot + cannbot-knowledge 工作区。依据是官方 Git 仓的固定提交、真实路径树、README、代表实现和 Agent 规则，未执行组件编译或 NPU 运行。

## 1. 结论与前轮范围修正

**这 27 个仓都包含相应软件组件的实际实现源码。** 它们构成 CANN 软件栈的不同部分；其中既有运行库和驱动，也有编译前端、头文件模板库、服务适配层及工具实现。分类页 `ai.gitcode.com/collections/cann/...` 是集合入口，与具体 Git 仓要区分。

前轮实际组装的 `workspace/` 是 **CANNBot direct 插件 + 知识能力 + 该插件的依赖**，不能称为覆盖整个 CANN 软件栈的开发工作区。产品源码还分布在本轮这些独立组件仓。不能用 CANNBot 三个核心仓的规则搜索结果推断所有组件仓都没有模块路由、设计治理或 CodeGraph。

本次存在正面证据：GE 根 AGENTS 按关键词/源码目录路由设计资料，并要求代码与设计同步；Runtime 技能允许优先使用已存在的 `.codegraph/`；HCCL/HCOMM 有架构权威文件和 RFC 流程。这些补充改变前轮比较的范围，但不证明已经存在与 AIoTBot 四张映射表完全相同的统一跨仓配置。

## 2. 27 个源码仓逐项核验

下表仓名链接固定到本轮读取提交的官方 README。代码路径来自同提交 Git 树；通信、领域/图引擎、编程/工具的代表实现正文和精确链接见文末本地审计。

| 层次 | 仓库与固定版本 | 真实实现职责 | 实际源码位置示例 |
|---|---|---|---|
| 算子 | [ops-nn](https://gitcode.com/cann/ops-nn/blob/955f8b33985b6d72989ebff341bb9c2c564a51bc/README.md) | 神经网络算子，如矩阵乘、激活、归一化 | `activation/`、`matmul/`、`norm/` 下的 `op_host/`、`op_kernel/` |
| 算子 | [ops-math](https://gitcode.com/cann/ops-math/blob/165d41f02a43a62324b434cb6bda7c533b14da3e/README.md) | 张量变换、基础数学、随机数等算子 | `conversion/as_strided/op_kernel/` 等 |
| 算子 | [ops-transformer](https://gitcode.com/cann/ops-transformer/blob/be33d95bb755cedec3108f70805c1874d1792540/README.md) | Attention、MoE、通信计算融合等算子 | `attention/`、`moe/`、`mc2/` |
| 算子 | [ops-cv](https://gitcode.com/cann/ops-cv/blob/bb717d075d129fd1fc7b96b2886824a1d153ed2f/README.md) | 图像处理、目标检测算子 | `image/`、`objdetect/`，含 Host/Kernel 实现 |
| 通信 | [hixl](https://gitcode.com/cann/hixl/blob/1737673b9c790df51792a94fb4974ee510f2cd92/README.md) | 单边点对点传输、KV Cache 数据分发 | `src/hixl/`、`src/llm_datadist/` |
| 通信 | [shmem](https://gitcode.com/cann/shmem/blob/ecea088d28c057e67181a313cf8abfa1dc777d8a/README.md) | 对称内存、跨设备远程内存访问与同步 | `src/host/`、`src/device/`、`src/host_device/` |
| 通信 | [hccl](https://gitcode.com/cann/hccl/blob/e8351f6ca326c18fe1fd734920f2d49a3ed735e1/README.md) | AllReduce 等集合通信算子、算法与执行器 | `src/ops/`、`src/common/` |
| 通信 | [hcomm](https://gitcode.com/cann/hcomm/blob/ba1e77785f4ee606ed759f938fa06031c1a7e559/README.md) | 通信域/拓扑/资源管理和基础通信原语 | `src/base_comm/`、`src/coll_communicator_mgr/` |
| 领域 | [sip](https://gitcode.com/cann/sip/blob/6705e8e0a9cc2094aebd63a701ace598c7aad84a/README.md) | FFT、BLAS、FIR 等信号处理加速 | `core/`、`ops/`、`sip_pta/` |
| 领域 | [ops-collections](https://gitcode.com/cann/ops-collections/blob/1fd35afd9298b8040666f42edfafbbd9ba552c2f/README.md) | NPU 容器模板库：map/set、位图、BloomFilter 等 | `include/detail/`；纯头文件也含真实算法实现 |
| 领域 | [ops-fft](https://gitcode.com/cann/ops-fft/blob/294cbc52e293f7387acc1609858b57d375444217/README.md) | FFT API、Plan 管理和算子实现 | `lib/fft_exec_api.cpp`、`src/rfft1_d/` |
| 领域 | [ops-gnn](https://gitcode.com/cann/ops-gnn/blob/1649557f16d0a8e29bc8dd0b44f5fd29155d05cc/README.md) | 图神经网络算子和 PyTorch 绑定 | `csrc/npu/`、`python/ops_gnn/` |
| 图引擎 | [ge](https://gitcode.com/cann/ge/blob/225dd7adb1504cee4e2e4aafdff11b893f64ce9e/README.md) | 计算图编译、优化和执行 | `compiler/`、`runtime/`、`api/` |
| 图引擎 | [metadef](https://gitcode.com/cann/metadef/blob/166a0edf20def71ba7ef877446da8463ca5a9e77/README.md) | 公共数据类型、图/算子定义、注册和运行上下文等基础能力 | `base/`、`inc/`、`pkg_inc/` |
| 图引擎 | [graph-autofusion](https://gitcode.com/cann/graph-autofusion/blob/34b41ee85c4162a83e04f326eac0db906d2fbc0f/README.md) | 图融合、代码生成、SuperKernel 等 | `autofuse/`、`super_kernel/`、`model_specialization/` |
| 图引擎 | [triton-inference-server-ge-backend](https://gitcode.com/cann/triton-inference-server-ge-backend/blob/87809b5f8844eb72adc1e90f43e6b9cd5c3b43c5/README.md) | Triton Inference Server 接入 GE/NPU 的后端实现 | `src/npu_ge.cpp`、`include/` |
| 编程 | [asc-devkit](https://gitcode.com/cann/asc-devkit/blob/a00678a7b18f74ddee76cb36500c5d16900c17b8/README.md) | Ascend C 开发套件、API 与架构相关实现 | `include/`、`impl/` |
| 编程 | [pyasc](https://gitcode.com/cann/pyasc/blob/076338c4a626090446413d98e0af835948c2e69c/README.md) | Python 前端、MLIR 方言/Pass、Ascend C 代码生成 | `python/asc/codegen/`、`lib/Dialect/`、`lib/Target/` |
| 编程 | [pypto](https://gitcode.com/cann/pypto/blob/88a359e5a97426907899bf2c2c027b5959448b20/README.md) | Tile 编程框架、编译 Pass、CodeGen 和运行调度 | `framework/src/`、Python 接口 |
| 编程 | [pto-isa](https://gitcode.com/cann/pto-isa/blob/56d3a18bca0b57e9e565e384a2c4459fff89a2ae/README.md) | Tile 指令库、CPU 模拟和 NPU 指令实现 | `include/pto/npu/`、`include/pto/cpu/` |
| 编程 | [atvoss](https://gitcode.com/cann/atvoss/blob/999805358318db9288c6e9e8c2e49e098ad4f8db/README.md) | Vector 融合算子 C++ 模板库 | `include/elewise/` 等 |
| 编程 | [catlass](https://gitcode.com/cann/catlass/blob/e420328d38945dea53ac8ee56795215db20b943b/README.md) | 矩阵/线性代数算子模板组件及 DSL | `include/catlass/`、`python/tla_dsl/` |
| 运行时 | [runtime](https://gitcode.com/cann/runtime/blob/494adaff232b823869f292d1b8100ecaf05948a1/README.md) | 设备、流、事件、内存、任务管理和维测 | `src/acl/`、`src/runtime/`、`src/dfx/` |
| 驱动 | [driver](https://gitcode.com/cann/driver/blob/e374b0dfdb9955634f575210727b2389ae71ba71/README.md) | 已开放的 DCMI、HAL、SDK-driver 组件 | `src/ascend_hal/`、`src/custom/`、`src/sdk_driver/` |
| 工具 | [asc-tools](https://gitcode.com/cann/asc-tools/blob/95eb681236ec63b419de176c077b4a6248e5c8b7/README.md) | CPU 调试、NPU 检查/性能采集、ELF 等工具 | `cpudebug/src/`、`npu_tools/` |
| 工具 | [oam-tools](https://gitcode.com/cann/oam-tools/blob/7cb3bad2bf7ef6ea710f71e46008d05c2d3450c7/README.md) | asys、msaicerr、msprof、hccl_test 等采集分析工具 | `src/asys/`、`src/msaicerr/`、`src/msprof/` 等 |
| 工具 | [amct](https://gitcode.com/cann/amct/blob/9d54d17e0942052193c827180dc43312c580acc7/README.md) | 量化、压缩、剪枝算法及 NPU 算子 | `amct_pytorch/algorithms/`、`amct_ops/` |

三个容易混淆的点：

- `ops-collections` 是真正的容器模板实现库；不能因为名字含 collections 就把它当仓库导航集合。
- GE 的“图”是计算图，HCOMM 的拓扑是通信拓扑，都不是 LLM 文档关系图或 CodeGraph 源码索引。
- 用户贴出的“AI 框架”“Framework Adapter”“毕昇编译器”是未附具体仓链接的标题，本轮没有据此认定其全部源码已公开。PyAsc 的 [compiler.py:141](https://gitcode.com/cann/pyasc/blob/076338c4a626090446413d98e0af835948c2e69c/python/asc/runtime/compiler.py#L141) 仍查找并调用外部 `bisheng`，不能拿 PyAsc 开源代替毕昇全量开源证明。

## 3. 在源码仓中实际找到的文档与规则

### GE：仓内已经有按模块路由、同步更新设计的规则

[GE AGENTS:75](https://gitcode.com/cann/ge/blob/225dd7adb1504cee4e2e4aafdff11b893f64ce9e/AGENTS.md#L75) 要求探索、问答、代码修改、设计/Spec 输出及检视时，按关键词、涉及目录或场景加载设计文档；代码修改后更新对应 `docs/zh/design/features/` 与 `modules/`。例如：

| 匹配线索 | 定位的仓内资料 |
|---|---|
| 图编译、优化 Pass、`compiler/` | `docs/zh/design/modules/compiler/compiler.md` |
| 动态执行、`runtime/v2/` | `docs/zh/design/features/unknown_shape_executor.md` |
| 显存、内存复用、memory 相关目录 | `docs/zh/design/constraints/memory-constraints.md` |

这是明确的知识/设计导航，功能上与我们的模块→资料路由有相似处；实现放在仓级 AGENTS Markdown 表中，不是已经核实的全生态统一 `config.yml`。这些文件仍属于 GE 仓内设计真源，不因为供 Agent 消费就自动变成 cannbot-knowledge 卡片。

### Runtime：源码、设计、Agent 技能共存，还有条件式 CodeGraph 使用

Runtime 完整工作树里有 `AGENTS.md`、`.agents/skills/`、`.claude/skills/` 和 [docs/zh/design/README.md](https://gitcode.com/cann/runtime/blob/494adaff232b823869f292d1b8100ecaf05948a1/docs/zh/design/README.md)，按架构、device/stream/task 等模块、AclGraph 等特性组织设计。

[runtime-llt-generator/SKILL.md:29](https://gitcode.com/cann/runtime/blob/494adaff232b823869f292d1b8100ecaf05948a1/.agents/skills/runtime-llt-generator/SKILL.md#L29) 明确存在 `.codegraph/` 时优先 CodeGraph，随后用 `rg` 核查磁盘。**本轮 clone 根实际没有 `.codegraph/`，没有运行或验收代码图。** 这证明规则支持可选代码索引，不能扩张成全 CANN 统一跨仓图服务，也不能继续笼统说 CANN 不使用 CodeGraph。

代表实现不是 README 里的示意： [stream.cpp:38](https://gitcode.com/cann/runtime/blob/494adaff232b823869f292d1b8100ecaf05948a1/src/acl/aclrt_impl/stream.cpp#L38) 定义 `aclrtCreateStreamImpl` 并调用底层流创建；Driver 的 [bbox_adapt.c:12](https://gitcode.com/cann/driver/blob/e374b0dfdb9955634f575210727b2389ae71ba71/src/ascend_hal/bbox/bbox_adapt.c#L12) 有实际平台相关实现。

### HCCL/HCOMM、PyPTO：组件内有自己的治理闭环

- HCCL/HCOMM 的根 AGENTS 指定仓内架构文档为权威，新功能经 Requirement Issue、SIG、`docs/zh/rfcs/` RFC 评审后进入实现与测试。[HCCL AGENTS:91](https://gitcode.com/cann/hccl/blob/e8351f6ca326c18fe1fd734920f2d49a3ed735e1/AGENTS.md#L91)、[HCOMM AGENTS:84](https://gitcode.com/cann/hcomm/blob/ba1e77785f4ee606ed759f938fa06031c1a7e559/AGENTS.md#L84)。
- PyPTO 审查 Skill 知识与本仓 docs/API/术语的一致性。这是本仓技能治理，不能把其中“知识库”一词直接解释成 cannbot-knowledge。[knowledge-checklist:13](https://gitcode.com/cann/pypto/blob/88a359e5a97426907899bf2c2c027b5959448b20/.agents/skills/pypto-skill-reviewer/references/knowledge-checklist.md#L13)。
- SHMEM 区分通信库实现与自定义算子开发 Skill；`design.md` 等工件限定在用户指定工程/示例里，不能默认写入核心源码或共享知识仓。[SHMEM .agents/README:50](https://gitcode.com/cann/shmem/blob/ecea088d28c057e67181a313cf8abfa1dc777d8a/.agents/README.md#L50)。

## 4. 与 AIoTBot workspace 图应怎样对应

以下是职责映射图，**不是宣称 CANN 官方规定或已在本机生成同名统一根目录**：

```text
AIoTBot 职责                         CANN 公开组件中的对应物
codebase/<各源码仓>/              →  ops-nn、hccl、ge、runtime、driver 等
  源码/测试/构建                 →  每个组件仓的 src/include/tests/build 等
  组件规则/设计导航              →  各仓 AGENTS、skills、docs/design、RFC
外层 agent/skills/workflows      →  cannbot、锁定的 cannbot-skills、安装到目标工程的插件
docs/raw*                        →  KB 文档归档、固定版本源码证据、任务输入（多种落点）
docs/spec/changes                →  具体开发流程的 requirements/spec/design/任务工件
docs/spec/specs                  →  可类比各组件长期规范/设计，但没有证明统一集中归档
docs/llmwiki                     →  cannbot-knowledge/knowledge/ 卡片 Bundle
Wiki 的格式、治理、索引规则      →  cannbot-knowledge/governance/、.agents/skills/ 等
顶层 AGENTS + config.yml         →  项目安装入口 + 仓内规则路由 + manifests/env/Registry
```

源码仓、组件设计/规范和稳定 Wiki 是三个不同资产层。用户已明确 AIoTBot 的 codebase 也是 main 下多组件、多代码仓，与 CANN 产品源码的多仓组成同类；不能把外层 workspace 集中呈现误判为单仓。CANN 组件文档经常与代码同仓，AIoTBot 主设计则将设计/规格集中于外层 docs。需要比较的是顶层如何选仓、局部规则怎样加载、规格真源在哪、哪些资料被选择成为知识，以及版本变化如何触发复核。进一步的知识系统对齐建议见 [架构对照第 10 节](aiotbot-cannbot-architecture-alignment-2026-09-30.md#10-按多仓实际布局对齐保留外层结构明确知识系统内部边界)。

消费有至少两条路径：①组件仓 AGENTS/Skill → 对应设计/API → 源码和测试核验；②项目知识入口 → cannbot-knowledge 检索 → 完整卡片 → 固定来源补证。不能把所有 CANN 开发活动都画成必须先经过共享 Wiki。

治理也分层：组件侧维护 RFC、设计、实现、测试及技能一致性；共享知识侧独立进行 ingest/审查/lint/索引更新。**本轮没有发现“这 27 仓的所有 docs/design/spec/task 自动搬进 knowledge/”的机制。** 前轮关于 SDD 原件不自动入 Wiki 的判断仍成立，但不能因此忽略各源码仓自己的设计资料。

版本管理另有 [release-management](https://gitcode.com/cann/release-management/blob/c847330e202fbe9e724ef36c6219e49f42cda312/README.md)。[9.1.0 发布说明:77](https://gitcode.com/cann/release-management/blob/c847330e202fbe9e724ef36c6219e49f42cda312/9.1.0/release-notes.md#L77) 列组合包、子包与仓标签的配套。它解决发布配套，不等同 workspace Agent 路由；本轮各仓 HEAD 与旧知识来源提交也不是一套已经构建验证的配套版本。

## 5. 本地到底拉了什么

全部位于 `E:/FactumCore/.scratch/cann-research-20260930/`，通过 `.git/info/exclude` 排除。没有设为 FactumCore 子模块，没有提交推送，没有修改 WiFi 主架构设计。

| 本地位置 | 获取状态 |
|---|---|
| `component-audits/runtime-driver/{runtime,driver}/` | 新增浅克隆，工作树完整；分别 7,269 / 4,909 个 tracked 文件 |
| `component-audits/release-management/` | 新增浅克隆，发布配套文档 |
| `component-audits/comm/`、`graph-domain/` | 共 12 仓 blobless 浅克隆、完整路径树、按需读取并保存代表文件；未展开完整工作树 |
| `component-audits/programming-tools/` | 8 个新浅克隆；其中 oam-tools 因 Windows 长路径 checkout 不全，已用 Git 对象读取取证；其余工作树展开，未递归全依赖 |
| `workspace/.cannbot/dependencies/ops-direct-invoke/asc-devkit/` | 复用此前实装依赖；本轮读取 HEAD 原文以避开安装清理过的文档工作副本 |
| `cannbot-knowledge/cann-ops-raw/ascendc/<repo>/<commit>/` | 复用原资源恢复脚本拉取的四个算子仓固定来源快照；不是四仓当前 HEAD |

27 仓都有本地 Git 证据；“有路径树和取证文件”不等于“27 仓都已完整 checkout/安装/构建”。完整工作树同样不意味着包含完整历史、全部子模块、闭源依赖或可运行硬件环境。

审计入口：[通信四仓](../../.scratch/cann-research-20260930/component-audits/comm/audit.md)、[领域/图引擎八仓](../../.scratch/cann-research-20260930/component-audits/graph-domain/audit.md)、[编程/工具九仓](../../.scratch/cann-research-20260930/component-audits/programming-tools/audit.md)、[Runtime 实际规则](../../.scratch/cann-research-20260930/component-audits/runtime-driver/runtime/AGENTS.md)、[Runtime 实际设计索引](../../.scratch/cann-research-20260930/component-audits/runtime-driver/runtime/docs/zh/design/README.md)。
