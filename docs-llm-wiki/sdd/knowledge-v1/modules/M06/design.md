# M06 代码双门禁：开发设计

## 接口与依赖

| 模块 | 文件 | 对外接口 | 依赖与边界 |
|---|---|---|---|
| M06 代码双门禁 | `S/checks.py`、`K/check.py,check.sh`；local/merge references；证明日志 | `check_local(final_view, context, verifier)` -> `LocalCheckRecord`；`check_merge(H,B,T,V, trusted_policy)` -> `MergeGateRecord`/逐 ClaimResult | 依赖 M01/M03/M04。只读检查，缺实证 incomplete；semantics/runtime 等义务需要真实方法和证据，未执行不得 pass。CI 独立输出、不 apply、不更新待审卡/锁/链接/业务代码 |

## 本模块拥有的文件与生成规则

| 路径 | 类别 | 开发动作 | 验收要求 |
|---|---|---|---|
| `skills/common/knowledge/_shared/checks.py` | F | 共用字段、来源、scope、断言、关系和目标树检查；local 读 final-view，merge 冻结 H/B/T/V 并产出逐断言记录 | 同一错误两模式诊断一致；merge 前后输入摘要不变；最新代码冲突失败；受检字节与报告严格绑定 |
| `aiot-wifi-knowledge/check.py` | F | 仅解析参数、加载框架版本并调用共享 CLI/Contract | 与共享 CLI 同输入得到同结果；输入文件摘要前后相同 |
| `aiot-wifi-knowledge/check.sh` | F | 定位本脚本目录后调用 check.py，并保留参数和退出码 | 含空格路径和失败退出码均正确转发 |
| `aiot-wifi-knowledge/.build/<operation_id>/reports/local-check.json` | R | 按 §4.3.1 的 G2C 顺序只读检查 final-view，写详诊断和 Claim 结果 | fail/incomplete 不可 apply；通过匹配全部最终字节 |
| `aiot-wifi-knowledge/logs/verifications/local/<check_id>.json` | R | 归档 LocalCheckRecord 及可恢复完整证明引用 | 精确内容可重建 local 索引，旧记录不覆盖新字节 |
| `aiot-wifi-knowledge/logs/verifications/merge/<gate_id>.json` | R | 从平台受信状态关联 gate、实际知识提交与证据包 | 错 head/过期 ref/不可恢复证据不能充作 shared 证明 |

完整职责与约束字段见 ../../traceability.json，同一路径只有一个主模块。F 为固定实现，D/R/X 是实例、产物或外部入口，P 首发延期；不得手造不存在的业务工程或成功证据。
