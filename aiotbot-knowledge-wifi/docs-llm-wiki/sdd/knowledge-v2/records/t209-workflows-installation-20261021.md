# T209：Workflow、受控安装与合入检查入口

范围：R215 / E215；安装定位部分同时覆盖 E203 的包身份边界。实现基线为 FactumCore `36fcafb57a746404696b177781f76353a3c8bd89`，分支 `codex/node-workflows`。本记录只描述本票编排、安装和薄入口子范围；完整真实节点包集成、独立审查及外部验收分别记录，不继承 knowledge-v1 成绩。

## 实现

- 生产模板为 5 节点，治理为 12 节点（含真实 `owner: user` Gate）。只使用 OpenFlow V1 字段；生产交接、发布交接均在本模板结束，不跨模板连边，不声称 Git/CI 已完成。
- Workflow exit ID 是路由名，condition 核实际 CLI 的 status/phase/data。文档走展示→真实人 Gate→认证动作记录→apply；代码走只读 local-check；未认证、等待、失败或 incomplete 均不成为批准。索引/回归失败不重复 apply，循环使用新 attempt。
- `install_catalog.py` 显式接收 source root、全新绝对安装目录、解释器和可选 workspace config。只复制 18 包及 2 模板，验证锁定依赖和包数据资源，不安装依赖、不执行源码、不写用户全局目录，不携带领域资料或运行状态。catalog 和 registry 只写安装私有区；OS ACL 与宿主注册另验。
- `check.py` 只从显式受信 catalog 调 merge-check 公开 CLI。缺输入返回 blocked/incomplete；handled exit 0 的 failed→2、incomplete→3，只有真实 `check_status=passed / phase=passed / mode=merge` 才返回 0。文档生产链不调用该入口；真实 CI 配置未知，未创建假 CI。
- `validate_design.py` 校验真实文件和引用、节点/owner/边、独立包产物义务。`tests/test*.py` 可按能力命名，不强迫同名测试文件；`default_location` 的合法附加字段不被过度拒绝。

## Red 与验证

先运行公开安装/模板/入口测试，缺失实现时安装成功断言、登记断言和缺依赖诊断断言失败；随后模板文件缺失、check.py 未实现的两条断言失败。初次缺实现时顺带通过的拒绝测试不算有效的安全证据；下述实现后回归重新实际覆盖。

运行环境：Python 3.12.14、PyYAML 6.0.2、pytest 8.4.2、ruff 0.11.13、Node 24.14.0、YAML npm 2.8.3。测试临时目录均在本 worktree 的 `K/artifacts/test-tmp/<本轮末级>`。

```powershell
$env:FACTUM_OPENFLOW_SOURCE = '<已核验固定源码目录>'
$env:FACTUM_POSIX_SHELL = '<显式选择的 Git Bash>'
<PYTHON> -m pytest aiotbot-knowledge-wifi/evals/tests/test_workflows.py skills/common/knowledge/hs-workspace-explore/tests/test_install.py --basetemp aiotbot-knowledge-wifi/artifacts/test-tmp/t209-final-3 -q
<PYTHON> -m ruff check aiotbot-knowledge-wifi/evals/validate_design.py aiotbot-knowledge-wifi/evals/tests/test_workflows.py aiotbot-knowledge-wifi/check.py skills/common/knowledge/hs-workspace-explore/scripts/install_catalog.py skills/common/knowledge/hs-workspace-explore/tests/test_install.py
```

结果：**22 passed，1 skipped**；ruff 通过。skip 为本账号不能创建普通符号链接；Windows junction 逃逸拒绝测试已实际通过。另已复核 T201 的 6 个定向反例（无约束 context、无绑定记录、重复 Target、跨芯片 pair、未锁 profiles）全部通过；该复核不代表本票执行了领域业务链。

固定兼容性检查实际执行 [OpenFlow 的 Workflow loader](https://github.com/Robin-hhc/OpenFlow/blob/1901a463efca222542a4634d7ce50c7b244b2bab/src/config/workflow-template-loader.js)、validator、registry、artifact loader 和 layout loader，源码身份为 `1901a463efca222542a4634d7ce50c7b244b2bab`。通过 GitHub contents base64 内容核 Git blob 身份后保存原字节；11 个传递源码文件的 SHA-256 固定在验证器中。使用两个真实模板与 18 个明确标记 synthetic 的完整合法包，结果 2 workflows / 18 skills / 18 artifact contracts。没有替换或模拟上游校验器。

负例覆盖：既存目标不覆盖，缺包或锁/依赖错误不发布，原件/私钥排除，资源引用越界与 junction 拒绝，真人 Gate owner 篡改/跨模板边/回归失败回 apply/错误 artifact exit 拒绝，包装器陈旧结果与包篡改拒绝，任意 cwd/空格与 Shell 失败码保留。

## 审查与剩余集成

标准轴自查：无 `_shared`、领域规则副本、根工具目录、私有跨包 import、自动 pip、原件写入或节点 Git 发布。规格轴自查：模板严格区分 CLI 处理成功与业务成功、真人动作与 Gate 字段、local handoff 与外部发布；没有把 prompt 当引擎重试上限或权限证明。

独立审查：**pending**。真实 18 包首轮联检识别到 7 个治理包仍采用旧自定义 artifact YAML，已交作者按固定 loader 标准修正；该次联检如实为 integration blocked，不算真实全包通过。完整代码包复制、真实仓外触发/人动作、六 Target、真实 CI/合入/跨组 ACL 及远端推送均未由本次静态/合成测试关闭。

此子范围测试结果为 tested；T209 全票暂为 in_progress，待作者合同修复、真实 18 包联检及独立审查后更新。提交 SHA 由本记录所属 Git commit 定位；实际合入与推送由 root 发布记录登记。
