# 知识库开发验证

知识测试统一在本目录，部署工具测试在 `repo/tools/deploy/tests/`。测试使用隔离合成资料，不读取受限 gold 或真实业务原件。

## 按业务职责组织

| 目录 | 验证内容 |
|---|---|
| `catalog/` | 卡头解析、来源身份、文件与卡双向关系、成功 hash、数据库重建 |
| `ingest/` | 单文件扫描、六决策落位、脚本检查、无卡成功、失败重试及删除 |
| `query/` | 精确词项、purpose、适用条件及公开查询行为 |
| `contracts/` | 继续复用的代码符号、来源定位、配置映射等独立算法 |
| `cli/` | doctor、命令错误与目标目录边界 |
| `workflows/` | 五节点顺序、作者与独立审阅职责、返工目标、能力包归属 |
| `integration/` | 仓内启动器的单文件调用和跨功能闭环 |
| `tooling/` | 测试发现、超时及 JUnit/汇总报告 |
| `support/` | 公共开发夹具和规则装载助手，不含业务测试 |

新增测试按功能放置。`stages/` 的旧八阶段套件、不可变视图、前序票据、应用事务 journal、索引代启用、跨轮恢复链及旧 Pipeline 助手随生产流程退场。保留的是可观察业务预期，不为保持历史测试数量继续约束已删除的机制。具体覆盖见 [SCENARIOS.md](SCENARIOS.md)。

## 执行

使用准备好的 Python 3.10–3.12 与本目录锁定依赖，从项目根 `repo/` 执行：

```text
python himate/himate-knowledge-wifi-mp/evals/run_acceptance.py --output-dir .scratch/acceptance-new
```

默认 full 自动发现当前含测试的功能目录，每组在独立进程完整收集；新文件无需登记到旧阶段清单。也可以使用：

```text
python himate/himate-knowledge-wifi-mp/evals/run_acceptance.py --groups ingest query --output-dir .scratch/focused-new
python himate/himate-knowledge-wifi-mp/evals/run_acceptance.py --profile quick --output-dir .scratch/quick-new
python -m pytest himate/himate-knowledge-wifi-mp/evals -q
python -m pytest tools/deploy/tests -q
```

quick 仅选每个功能目录排序后的首个测试文件，是明确的局部冒烟。`--groups` 同样是局部范围；验证按实际修改范围选择，不把每次局部工作都扩成全量测试。部署依次执行一次锁定依赖的 pip 安装、删除本次全部同名 Skill 和 Workflow 包目录、复制全部新包，宿主加载运行，不在每次安装后追加验证。

输出目录必须全新。运行器保留每组 JUnit、stdout/stderr、实际选择和 `summary.json`；超时、收集失败、空测试组和无效报告不能算通过。`--jobs` 控制测试组并行，不表示生产 ingest/lint 支持并发写入。性能统计只作观察，不设速度门禁；`--baseline` 仅在环境和选择一致时比较。

## 验证边界

独立算法检查、隔离 CLI 测试和公司实际环境分别记录。`tools/deploy/tests/test_install_skills.py` 仅用临时目录和模拟 pip 验证三步顺序、pip 失败时旧包保留、同名包完整替换、其他包与源码保留及解释器选择；部署不分发知识仓或 ZIP。该冒烟不代表真实安装环境、OpenFlow 宿主触发或业务知识验收。

P2、P3 由作者执行，P4 由独立 reviewer 读计划、旧卡、新稿和依据。合成脚本测试可以验证角色与返工配置，不能替代真实内容审阅质量。真实 Linux、公司文档、代码实现和权限效果由实际试用单列验收。

共享设计维护当前行为；本地 `../docs-llm-wiki/sdd/` 保存历史设计和验证记录。历史成绩不并入当前通过数，运行产物不写入 Skill。
