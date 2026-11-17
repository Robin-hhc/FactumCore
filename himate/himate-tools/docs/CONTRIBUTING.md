# 开发与贡献

开发前从[工具入口](../AGENTS.md)和[开发文档](README.md)定位规则，结合领域知识仓中的设计、当前源码及适用测试确定修改范围。

工具根的 `runtime/` 提供 CLI、业务执行和共用规则。独立的 `himate-skills/` 维护 `skills/` 和 `workflows/`。Skill 提供节点操作、参考和写作模板，Workflow 维护节点顺序、角色、交接与出口。知识数据由命令的 `--knowledge-root` 指定。开发测试在 `evals/`，部署测试在 `evals/deploy/`，部署实现和离线模型在 `distribution/`。

通过公开 CLI 验证单文件入库、引用查询、六决策、整卡检索、旧卡读取、P4 返工和 P5 重试，按变更范围选择测试。新卡字段与旧知识迁移以[卡片规范](../runtime/governance/specs/cards.md)为准；读取和重建索引不批量改写正式卡或推进来源处理版本。业务行为测试与独立算法测试分别组织，执行方式见 [evals/README.md](../evals/README.md)。测试、文档与发行锁随对应行为一同更新。

部署从工具包运行，使用已有 Python 3.10–3.12。能力源码默认取同级 `himate-skills/`，也可用 `--capabilities-root` 或 `-CapabilitiesRoot` 指定。部署处理三个能力安装目录和 `runtime/requirements.lock.txt` 的依赖，传入知识根时为该库准备 `artifacts/models/docling-cpu/` 的模型。准备完成后才替换同名能力包。知识根的 `config.yml` 与 `AGENTS.md` 由项目维护者直接编辑。部署实现和参数见[部署说明](DEPLOY.md)。解析默认使用 native，standard OCR 需显式配置。依赖兼容、模拟部署和真实 OCR 验证分别记录。共享示例使用 `repo/` 示意 manifest 工作区根，路径注明相对基准。

Git历史与提交在文件所属的实际Git仓执行，多仓同步按配置的manifest根执行，该根不要求有.git。提交推送依用户授权；保留其它任务修改，不提交凭据、跨组资料、测试产物或无关本机资料，不读受限gold。合成测试、宿主对接与公司资料效果分别报告。
