# 开发与贡献

开发前从[领域入口](AGENTS.md)和[文档路由](docs-llm-wiki/README.md)定位规则，结合当前共享设计、源码及适用测试确定修改范围。

业务执行与共用算法在runtime/governance，Skill只写必要指引与reference，Workflow只维护顺序、角色和出口。以上目录均相对知识根；skills、workflows和tools也位于知识根内。开发测试统一在evals，部署工具测试位于evals/deploy；tools/deploy保留部署实现、说明与离线模型包。

通过公开 CLI 验证单文件入库、引用查询、六决策、整卡检索、旧卡读取、P4 返工和 P5 重试，按变更范围选择测试。新卡字段与旧知识迁移以[卡片规范](governance/specs/cards.md)为准；读取和重建索引不批量改写正式卡或推进来源处理版本。业务行为测试与独立算法测试分别组织，执行方式见 [evals/README.md](evals/README.md)。测试、文档与发行锁随对应行为一同更新。

部署从知识根运行，使用已有 Python 3.10–3.12。两个平台先交互确认 OpenFlow Skill、CAC Skill 和 OpenFlow Workflow 的目标目录，并收集已有项目入口的覆盖选择，默认 y，n 保留。确认后默认安装 `runtime/requirements.lock.txt` 的 CPU OCR 依赖，并准备 `artifacts/models/docling-cpu/`；完整模型复用，否则优先验证 `tools/deploy/models/manifest.json` 与随包权重后离线复制，损坏时停止。未携带权重时才预置，或显式 `--download-models` / `-DownloadModels` 下载。依赖和模型准备均成功后才删除本次同名包、复制新包，再将知识根内的 config.yml 与 AGENTS-code-root.md 按选择复制为 ../../ 的项目入口。源模板和其他包保留，准备失败不动旧包或入口。解析默认仍为 native，standard OCR 需显式配置；依赖兼容、模拟部署和真实 OCR 验证分别记录，不把单一执行端结果推广为跨平台验收。共享示例使用 `repo/` 示意 manifest 根，并明确相对基准。

Git历史与提交在文件所属的实际Git仓执行，多仓同步按配置的manifest根执行，该根不要求有.git。提交推送依用户授权；保留其它任务修改，不提交凭据、跨组资料、测试产物或无关本机资料，不读受限gold。合成测试、宿主对接与公司资料效果分别报告。
