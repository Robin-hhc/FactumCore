# 独立事件与来源限制

只在明确的维护请求下选择动作；日常增量治理使用 `hs-knowledge-lint` Workflow，只读引用报告见[audit](audit.md)。

```text
python K/knowledge.py maintain --action <动作> --input REQUEST.json --json
```

| 动作 | 输入 | 用途 |
|---|---|---|
| `inspect-context` | `operation_id` | 只读观察采用来源、受影响Claim、依赖和限制 |
| `status` | `operation_id` | 读取已记录限制及未完成事件 |
| `register-source-change` | `operation_id`、实际 `bundle_ref` | 从来源锁与固定捕获包登记来源变化 |
| `register-code-change` | 同上 | 另核当前授权代码字节与路径后登记变化 |
| `recover-events` | `operation_id` | 完成已有确切pending来源事件 |
| `advance` | `operation_id` | 复验当前卡与来源，解除已解决的机械来源新鲜度限制 |

独立事件与advance有正式写入效果；只执行用户明确要求的动作。ingest捕获产生的是暂存事件，P6才发布，不再额外登记一次。所有写入复用CLI的锁与实际字节检查。

inspect-context保持真实用途：确切历史依据可恢复时，不因当前代码漂移自动给historical施加当前新鲜度义务；guidance符号导航与当前字节分开观察。固定旧依据缺失、语义/适用性限制和未授权范围仍保留。普通raw限定范围不额外读取无关dbox；当前地址不可用与固定证据丢失分开报告。

advance只解除已被实际来源复验解决的机械限制，不表示完成独立审阅或证明技术正确；未知代码/配置、语义及适用性限制不因字节相同而解除。不要手改事件、水位或历史指纹以取得成功结果。
