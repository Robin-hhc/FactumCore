# 独立索引与共享快照

正常 batch 已完成适用索引收尾。本页用于明确要求的索引维护，不能因普通查询空命中自动执行。

## 独立索引动作

调用 `python K/knowledge.py apply --action ACTION --input REQUEST.json --json`：

| 动作 | 关键业务输入 | 作用 |
|---|---|---|
| `index-build` | 实际正式知识与采用材料，可选 `channel` | 构建并完整验证不可变候选代，返回 `generation_ref` 和原 `expected_active`，尚不激活 |
| `index-verify` | 确切 `generation_ref` | 核完整数据库、卡正文、版本与指纹，不激活 |
| `index-activate` | 确切 `generation_ref`、原 `expected_active` | 复核真实输入与写屏障，在写锁下 CAS 切换活动代 |

使用返回的确切引用，不从目录名猜代次或替换原基线。规则改变后需要显式重建派生索引；旧代次保持原字节。完整核验由 CLI 执行，无需 Agent 手工复现表格／行值校验。

## 代码与采用材料

有实际构建／运行依据时，可通过按卡 ID 组织的 `code_contexts`（兼容名 `code_evidence`）固定 `code_identity`、`config_digest` 和逐 Claim 的 `claim_evidence`。每项材料保留 requirement、path、sha256；来源和条件必须真实，不能从 passed 声明合成证据。

静态源码 Claim 继续按实际配置与文件核验。构建、运行或配置材料发生变化时，源文本未变也不代表结论仍可用于当前问题。索引动作不重跑 P4 内容判断。

## 共享仓库快照

`channel:"shared"` 可指定真实 Git 的 `knowledge_commit`，取得 `repository_snapshot`。它核实际提交中的卡、规则、来源锁与内容关系，不代表发布者身份、CI 或远端合入已经通过。

只有任务明确提供 `publication_receipt_ref` 以声明签名发布身份时，才使用现有受信适配器核该声明。普通本地索引或直接仓库快照不要求签名部署，不进行网络发布或 Git 写入。

无生产者私有缓存的消费端从正式卡、记录与证据重建索引；当前代码用途仍须核实际代码、配置和 Claim 范围，历史快照不直接证明当前实现。
