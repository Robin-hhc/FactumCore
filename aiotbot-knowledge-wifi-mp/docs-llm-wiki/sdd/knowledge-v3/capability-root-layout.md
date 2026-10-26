# 配套能力迁至项目根

用户确认复用 FactumCore 根已有的 `AGENTS.md`、`config.yml`，将 Skill／Workflow 移至同级 `skills/`、`workflows/`，移除重复的 `project-root-files/`。迁移基线为 `2e5f8f73e86ec394097e0fe1d0c1e742cff404b7`。

## 需求与边界

```text
FactumCore/
├── AGENTS.md / config.yml
├── skills/common/knowledge/
├── workflows/common/knowledge/hs-knowledge-ingest/
├── main/                              本仓既有业务代码工作区
└── aiotbot-knowledge-wifi-mp/           原件、知识、规则、记录和系统文档
```

- 根入口补充日常知识任务与代码回源职责，保留原开发和数据边界。
- 根配置只补说明，保持实际 workspace 身份、知识库路径和未知业务映射；不使用模板的 `root: .` 覆盖当前 `null`。
- 迁移只改变能力位置及其定位方式，不改变 ingest、lint、query、真实确认、代码内容复核或人工上库流程。
- [查询调整设计](background-retrieval-design.md)仍待确认；本次不实施完整正文返回、来源批次恢复或轻量 API。
- 历史 SDD、冻结设计、来源、治理规则和现有业务代码保留原字节。旧记录中的能力路径按当时提交解释。

## 修改落点

| 落点 | 适配 |
|---|---|
| 根 `skills/`、`workflows/` | 移动既有包；单包内部和兄弟能力的相对结构保持 |
| `hs-workspace-explore/scripts/install_catalog.py` | 从根目录查找能力和模板，仍生成新的固定摘要安装结果 |
| Skill tests、`evals/` | 更新仓根层级、包发现、夹具路径、真实 Workflow loader 入口和安装验证 |
| `.gitattributes` | 新位置继续保留能力原字节，避免换行转换改变包指纹 |
| 现行 AGENTS、架构与详细设计、使用说明 | 同步目录、路径基准和入口；保持流程与决策语义 |

来源、正式卡、运行记录、治理契约和规则锁位置不变；不保留第二份可执行能力或路径回退副本。

## 验证

迁移前保存了 282 份能力文件、267 份规则／历史／原件及入口文件和 593 份既有业务文件的指纹；其中 docs-raw/AGENTS.md 仅更新能力路径，其余 266 份保持原字节。本机详细清单在 `.scratch/rootlayout-20261026/baseline.json`，其中业务文件含原有占位文件，不代表新增源码或全部提炼。

| 范围 | 验证要求 |
|---|---|
| 安装与发现 | 新位置实际安装 20 个 Skill／1 个 Workflow，源包、安装包、catalog 摘要一致；E0 仍读取根入口与知识根 |
| 流程 | 使用固定 OpenFlow loader 与现有公开 CLI 回归，检查路径移动后入库、治理和查询机制 |
| 文档 | 当前入口、链接和 Mermaid 有效，2.1 主流程及业务决策不随目录迁移变动 |
| 字节保护 | 逐文件核对受保护清单及业务代码；能力中仅必要的定位代码、测试和说明发生变化 |
| 范围 | 定向测试、完整回归与部署事实分别记录；不把包安装等同于内部 Agent 或公司环境接入 |

完整回归 21 组、380 项，379 通过、1 跳过、0 失败／错误；跳过项为当前 Windows 账号普通符号链接权限，已有 junction／越界拒绝用例通过。新布局实际安装 20 个 Skill／1 个 Workflow，源包、安装包和 catalog 摘要一致；固定 OpenFlow loader 实际加载 20 个 Skill、24 个 Contract 和单一 ingest 工作流。Ruff、102 处本地链接和 33 张 Mermaid 检查通过，2.1 主流程原字节不变，标准轴与规格轴复核无阻断。

可分发结果见[验证汇总](records/capability-root-layout-20261026.json)，完整原始测试在本机 `.scratch/rl26a/`。旧安装器对新布局的预期失败和定向回归保存在 `.scratch/rootlayout-20261026/`；定向测试不累计到完整回归用例数。历史成绩不重写，这些结果不等同于公司内网部署或真实宿主运行验收。
