# 开发与贡献

开发前从[工具入口](../AGENTS.md)和[开发文档](README.md)定位规则，结合领域知识仓中的设计、当前源码及适用测试确定修改范围。

工具根的 `runtime/` 提供 CLI、业务执行和共用规则。独立的 `himate-skills/` 维护 `skills/`、`workflows/`、能力安装脚本及对应测试。Skill 提供节点操作、参考和写作模板，Workflow 维护节点顺序、角色、交接与出口。知识数据由命令的 `--knowledge-root` 指定。开发测试在 `evals/`，npm 安装与运行环境测试在 `evals/deploy/`，npm 实现和离线模型在 `distribution/`。

业务 Skill 保留可独立指导本机或 SSH CLI 的任务方法、内容判断和模板，MCP 是可选的宿主工具适配；Setup 只准备实际执行端的 CLI 与依赖，不要求为所有 harness 注册 MCP。修改接口时同时核对 CLI-only 和 MCP 两种用法：参数、路径基准和返回值语义与运行实现一致，宿主额外缩限和工具授权由适配层明确保留。已采用 MCP 的受控任务按原工具诊断恢复，不以 CLI 入口绕过拒绝或 `blocked`。

通过公开 CLI 验证单文件入库、引用查询、六决策、整卡检索、旧卡读取、P4 返工和 P5 重试，按变更范围选择测试。新卡字段与旧知识迁移以[卡片规范](../runtime/governance/specs/cards.md)为准；读取和重建索引不批量改写正式卡或推进来源处理版本。业务行为测试与独立算法测试分别组织，执行方式见 [evals/README.md](../evals/README.md)。测试、文档与发行锁随对应行为一同更新。

用户通过 npm 安装 CLI，通过 `knowledge setup` 安装锁定的基础依赖。文档解析和 OCR 按需准备。模型包安装脚本校验并合并本机 OCR 资产，解析默认使用 native，standard OCR 使用本机模型或显式配置的知识库内模型。能力仓的 deploy 脚本使用 Python 标准库复制其自身的 Skill 和 Workflow 包。知识根的 `config.yml` 与 `AGENTS.md` 由项目维护者直接编辑。工具安装参数见[安装说明](DEPLOY.md)，能力安装参数见[能力仓说明](../../himate-skills/README.md)。依赖安装、能力复制和真实 OCR 验证分别记录。共享示例使用 `repo/` 示意 manifest 工作区根，路径注明相对基准。

Git历史与提交在文件所属的实际Git仓执行，多仓同步按配置的manifest根执行，该根不要求有.git。提交推送依用户授权；保留其它任务修改，不提交凭据、跨组资料、测试产物或无关本机资料，不读受限gold。合成测试、宿主对接与公司资料效果分别报告。
