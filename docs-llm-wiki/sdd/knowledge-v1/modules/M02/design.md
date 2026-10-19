# M02 项目发现绑定：开发设计

## 接口与依赖

| 模块 | 文件 | 对外接口 | 依赖与边界 |
|---|---|---|---|
| M02 项目发现绑定 | `S/workspace.py`；workspace 配置、用户级 registry/托管薄规则；explore reference | `resolve_project(path, base, registry, authority) -> ResolvedBinding`；`load_context(binding, reader) -> ProjectContextReceipt` | 依赖 M01。resolved 与 context_loaded 分开；后者带实际入口字节摘要/读取轨迹，输出实际内容供宿主加载。只写获准缓存/回执，不扫描整盘、不启动摄入 |

## 本模块拥有的文件与生成规则

| 路径 | 类别 | 开发动作 | 验收要求 |
|---|---|---|---|
| `config.yml` | F | 在既有 `repos / architecture / wiki_entities / symbol_aliases` 结构上扩展 workspace 身份、领域根、模块边界、Target 与 pair 引用、渠道默认值、工具/契约政策引用 | 配置 Schema 通过；六 Target/三 pair 均能解析且不虚构代码目录；共享 Host 路径返回多芯片候选；冲突和悬空引用返回明确诊断 |
| `config.local.yml` | L | 只允许覆盖 Schema 明确列出的物理根、运行时位置等本机字段；加载后生成合并配置摘要 | 合法路径覆盖有效且不改公共配置；越权字段拒绝；CI 不依赖开发者本机文件；无文件时公共配置仍可解释 |
| `<user-agent-home>/workspace-registry.json` | L | 安装/挂载或配置更新时登记 workspace_id、config 定位及摘要、登记版本和由配置生成的路径匹配索引 | 任意 cwd 给出已登记代码文件可定位；迁移/失效配置被识别；同远端不同 checkout 不误用缓存；未登记时报告缺口 |
| `skills/common/knowledge/_shared/workspace.py` | F | 实现真实路径/仓身份/有限登记匹配、配置合并摘要、入口清单与读取回执核验、绑定刷新 | 仓外/嵌套/多 clone/worktree/导出均按身份区分；路径跳转不扩权；未知项目无假成功 |
| `skills/common/knowledge/_shared/tests/test_workspace.py` | F | 合成目录覆盖仓外、相对路径、联接点、worktree、多映射、入口变化/不可达、授权 epoch 和两阶段回执 | 确定性绑定、失败关闭和缓存失效用例全部通过；无整盘扫描或业务读写 |

完整职责与约束字段见 ../../traceability.json，同一路径只有一个主模块。F 为固定实现，D/R/X 是实例、产物或外部入口，P 首发延期；不得手造不存在的业务工程或成功证据。
