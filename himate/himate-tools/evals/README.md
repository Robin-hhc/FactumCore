# 知识库开发验证

业务、共用算法与部署工具测试统一在本目录，部署测试位于 `deploy/`。测试使用隔离合成资料，不读取受限 gold 或真实业务原件。

## 按职责组织

| 目录 | 验证内容 |
|---|---|
| `catalog/` | 卡头解析、来源身份、文件与卡双向关系、成功 hash、数据库重建 |
| `ingest/` | 单文件扫描、六决策落位、脚本检查、无卡成功、失败重试及删除 |
| `query/` | 整卡精确词项、AND 标签、排序、显式退役筛选、完整读取、旧参数错误及搜索缓存升级 |
| `contracts/` | 继续复用的代码符号、来源定位、配置映射等独立算法 |
| `cli/` | doctor、命令错误与目标目录边界 |
| `workflows/` | 五节点顺序、作者与独立审阅职责、返工目标、能力包归属 |
| `integration/` | 工具包 CLI 对独立知识根的调用和跨功能闭环 |
| `deploy/` | 能力包替换与目录保护、Linux/PowerShell 参数和退出码、CLI npm 升级，以及模型 npm 包的完整性与分片合并 |
| `tooling/` | 测试发现、超时及 JUnit/汇总报告 |
| `support/` | 公共开发夹具和规则装载助手，不含业务测试 |

新增测试按功能放置，以可观察业务行为为预期，不按历史测试数量约束实现。旧卡与历史来源的有效兼容行为继续验证；用途/Claim 资格门不属于新搜索契约。具体覆盖见 [SCENARIOS.md](SCENARIOS.md)。

## 执行

使用准备好的 Python 3.10–3.12 与本目录锁定依赖，从项目根 `repo/` 执行：

```text
python himate/himate-tools/evals/run_acceptance.py --output-dir .scratch/acceptance-new
```

默认 full 自动发现当前含测试的职责目录，包括 `deploy/`，每组在独立进程完整收集；新文件无需登记到旧阶段清单。也可以使用：

```text
python himate/himate-tools/evals/run_acceptance.py --groups ingest query --output-dir .scratch/focused-new
python himate/himate-tools/evals/run_acceptance.py --groups deploy --output-dir .scratch/deploy-new
python himate/himate-tools/evals/run_acceptance.py --profile quick --output-dir .scratch/quick-new
python -m pytest himate/himate-tools/evals/ingest -q
```

Workflow 和跨节点 CLI 验证默认从工具包旁的 `himate-skills/` 读取能力源码。能力源码另存时，验收入口与 `evals/validate_design.py` 都支持 `--capabilities-root <能力源码目录>`。直接运行这组 pytest 时也可通过测试环境变量 `HIMATE_TEST_CAPABILITIES_ROOT` 提供该目录。报告中的测试路径相对工具根。仅有独立工具包时，实际检查组合工作区 Git 忽略规则的用例标记为跳过。

quick 仅选每个职责目录排序后的首个测试文件，是明确的局部冒烟。`--groups` 同样是局部范围；验证按实际修改范围选择，不把每次局部工作都扩成全量测试。`knowledge setup` 沿用 pip 配置安装锁定的依赖，模型 npm 包校验并准备本机模型，deploy 脚本替换本次同名 Skill 和 Workflow 包目录，由宿主加载。具体操作见[部署说明](../docs/DEPLOY.md)。

输出目录必须全新。运行器保留每组 JUnit、stdout/stderr、实际选择和 `summary.json`；超时、收集失败、空测试组和无效报告不能算通过。`--jobs` 控制测试组并行，不表示生产 ingest/lint 支持并发写入。性能统计只作观察，不设速度门禁；`--baseline` 仅在环境和选择一致时比较。

## 验证边界

独立算法检查、隔离 CLI 测试和公司实际环境分别记录。[deploy/test_install_skills.py](deploy/test_install_skills.py) 与 [deploy/test_posix_deploy.py](deploy/test_posix_deploy.py) 使用临时目录和解释器记录器，验证纯能力包安装、同名包完整替换、其他包与源码保留，以及 Linux/PowerShell 的解释器选择、参数与退出码传递。依赖安装和模型包分别由环境测试、npm 测试覆盖。真实 OCR 结果按实际执行端记录，模拟测试通过不代表实际宿主或业务知识验收通过。

P2、P3 由作者执行，P4 由独立 reviewer 读计划、旧卡、新稿和依据。合成脚本测试可以验证角色与返工配置，不能替代真实内容审阅质量。真实 Linux、公司文档、代码实现和权限效果由实际试用单列验收。

领域知识库的 `docs-llm-wiki/` 维护使用说明与当前设计。工具包内的 [面板 CLI 契约](../docs/面板CLI契约.md) 定义宿主接口，本地 `../docs/sdd/` 保存历史设计和验证记录。历史成绩不并入当前通过数，运行产物不写入 Skill。
