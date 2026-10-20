# 以最新 §5.3 统一命名与路径（2026-10-20）

用户明确所有命名、路径以当前《AIoTBot知识库架构设计》§5.3 为准。输入版本为 `0eb631ec7ace819867b73755989df46c842f5418`；本次保存该节原始字节，SHA-256 为 `4c061504623a48faea1a35785c89589adfe1d1276b3c2d3febb9b7df90873d1f`。不改写该节，不重构架构或三条生命周期图。

## 本次对齐

- 主设计入口统一为 `aiot-wifi-knowledge/docs-llm-wiki/AIoTBot知识库架构设计.md`，同步根/领域导航、详设、活跃 SDD 与 Git 原字节属性。
- 两个 Workflow 移到 `workflows/common/knowledge/hs-common-knowledge-ingest/`、`workflows/common/knowledge/hs-common-knowledge-lint/`；四 Skill 仍在 `skills/common/knowledge/`。全部保持空占位。
- `docs-raw/sources/{dbox,3ms,wiki}/` 按 §5.3 建立空目录，仅 `.gitkeep`；详设/SDD 对应的三项未来路径从旧 `.md` 名称改为目录，不启用抓取或链接更新，状态仍为 deferred。
- 主设计其他章节的 `.skills/`、`.workflows/`、`aiot-knowledge/` 旧称按 §5.3 修正；WiFi 领域直接位于 FactumCore 根，不增加中间层。
- 详设图标签、完整目录树、文件表、Workflow 类型与路径标识，以及 T20/T21、M09 和 traceability 三项 Workflow 路径同步；不引入自行命名的 `*-workflow` 注册别名。
- main 仍只保存空占位。`bfgx/dpa/mp1x/mp12` 等采用 §5.3 的物理示意命名；既有 chip12/chip08/chip07c 为未绑定的逻辑 Target，不猜测二者对应关系，不修改空业务映射。

当前 §5.3 的 `knowledge/` 仍列七类正文；模板数量表述不提供其他 Profile 名称，本次不虚构新卡类型。§5.3 未列的旧执行程序路径仅保留为待对齐方案；不恢复已归档的 `_shared` 或根 tools/开发环境。

## 基线与历史边界

同步 baseline 当前主设计名、两份来源摘要和 naming_authority；traceability 回算全部 182 个来源行号，维持 18 需求、9 模块、28 任务、148 路径、34 验收及 49 条依赖关系。既有任务与验收状态不改变，当前部署仍为 skeleton_only。

历史 records、baseline 既往修订、previous_sources 及仓外归档身份不做批量改名；这些路径描述当时提交，不属于当前导航。此前已归档实现与历史验证成绩保持历史身份。

本次变更前快照在仓外归档 `naming-align-20261020-145740/tracked-before.zip`，SHA-256 为 `5e0dd473cfc547616b56deec87addf5878364b99cbca8abc508184d1830d31d5`。本次只作路径与文档校验，不运行已移出的功能程序。结果见 [naming-paths-verification.json](naming-paths-verification.json)。
