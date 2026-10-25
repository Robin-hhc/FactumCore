# 兼容范围

本包保留旧版签名语义复核协议，仅在调用方明确需要兼容能力时执行。现行流程在 P3/P4 完成必要语义核验，P5 使用只读 `hs-knowledge-lint`；现行 CI 入口是可信基线的领域 `check.py`，不会委托本包。

旧安装 catalog、操作 FinalView 与 signed semantic evidence 的校验继续保留；缺真实人或代码证据仍不通过。包存在不代表固定 CI、宿主触发或权限策略已经部署。新接入遵循 `governance/specs/ci-runner.md`。
