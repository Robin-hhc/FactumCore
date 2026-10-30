# 开发与贡献

开发前从[领域入口](AGENTS.md)和[文档路由](docs-llm-wiki/README.md)定位规则，结合当前共享设计、源码及适用测试确定修改范围。

业务执行与共用算法在runtime/governance，Skill只写必要指引与reference，Workflow只维护顺序、角色和出口。业务测试统一在evals；部署工具测试在repo/tools/deploy/tests。

通过公开 CLI 验证单文件入库、引用查询、六决策、P4 返工和 P5 重试，按变更范围选择测试。业务行为测试与独立算法测试分别组织，执行方式见 [evals/README.md](evals/README.md)。测试、文档与发行锁随对应行为一同更新。

部署脚本负责复制 Skill 和安装依赖，运行端独立取得仓库代码，Workflow 由宿主导入。共享示例使用 `repo/` 和明确基准的相对路径。

Git在项目根执行，提交推送依用户授权；保留其它任务修改，不提交凭据、本机配置、跨组资料或测试产物，不读受限gold。合成测试、宿主对接与公司资料效果分别报告。
