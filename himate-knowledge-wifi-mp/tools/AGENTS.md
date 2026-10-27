# 知识库本地工具

本目录保留已有固定工具和部署回归。`deploy/` 内私有环境安装器、登记工具和 runner 仅用于既有部署兼容或开发验证，不是正常首次使用流程。

正常入口在已安装 `hs-knowledge-explore` Skill 的 `scripts/setup.py`：默认使用当前全局 Python，已齐依赖就直接读取根 `config.yml`，缺项才安装到同一解释器。跨机器信息放 Skill 自己的 `config.env`，由 Agent/harness 通过 SSH 执行和检查，不另建 runner 或工具副本。

项目配置全部由用户维护在根 `config.yml`；稿件、请求、记录、索引和报告继续放 K 已有 `.build/`、`logs/`、`artifacts/`。不把 catalog／registry／binding 变成用户手填或初始化步骤。节点保留本职业务检查及领域固定规则，OpenFlow 负责流程交棒。

工具不从原件取得执行或发布授权，不自动改变宿主或运行 Git。测试使用隔离材料，不读受限 gold，不覆盖已有环境；本项目 SDD 和历史验证记录保留原字节，仅在本地维护。

Skill 可人工逐个调用，只校验本职业务数据和固定检查；OpenFlow 负责流程顺序、角色隔离及交棒合法性。节点不要求 Workflow 身份、catalog 登记或上游通过凭证。
