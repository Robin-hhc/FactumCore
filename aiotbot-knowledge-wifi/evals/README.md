# 节点机制验收

此目录保存当前 v2 的领域契约、Workflow 和跨包公开 CLI 联检。各 Skill 的单元测试在本包 `tests/` 中，分别启动 Python 进程，避免同名私有模块的测试导入互相污染。只使用隔离合成材料和测试密钥，不读取受限 gold。

使用 Python 3.12 和显式锁定环境，执行 `python evals/run_acceptance.py --output-dir <全新本机结果目录>`。保留每组 JUnit、stdout/stderr 和汇总 JSON；退出码不能替代逐项报告。可选环境 `FACTUM_OPENFLOW_SOURCE` 指向验证器固定 SHA 的上游源码，`FACTUM_POSIX_SHELL` 指向实际 POSIX Shell；缺少时相关检查明确 skipped，不算通过。安装器由 workspace-explore 提供，不自动安装依赖或修改全局宿主配置。

`test_node_pipeline.py` 串联 raw、候选、精确原文展示、合成认证事件、stable、索引和查询。签名测试只验证绑定/拒绝机制；真实人动作、真实宿主隐式触发、六 Target/三 pair、真实 CI 合入与权限验收位于 T211，缺少输入时保持 pending。历史 knowledge-v1 的成绩不合并到当前计数。
