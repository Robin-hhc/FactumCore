# M08 持续治理：开发设计

## 接口与依赖

| 模块 | 文件 | 对外接口 | 依赖与边界 |
|---|---|---|---|
| M08 持续治理 | `S/maintenance.py`；events/watermarks；运维规范 | `impact(event, graph)` -> 持久影响/阻断；`reconcile(event, matching_proof, channel)` -> 分渠道恢复；`current_state()` 提供有效性 epoch | 依赖 M01/M03/M04，恢复依赖 M05/M06/M07。source/requires/derived_from 条件化传播，related_to 不全量传播；先阻断再推进扫描水位，修卡/证明/激活齐备再推进应用水位 |

## 本模块拥有的文件与生成规则

| 路径 | 类别 | 开发动作 | 验收要求 |
|---|---|---|---|
| `skills/common/knowledge/_shared/maintenance.py` | F | 实现 event 幂等、反向 requires/derived_from 遍历、事务写入影响与水位、复核记录匹配和 reconcile | 重放不重复；中断不漏影响；旧索引仍执行新阻断；只有匹配新证明后恢复适用性 |
| `skills/common/knowledge/_shared/tests/test_maintenance.py` | F | 构造直接/传递依赖、无关关系、重复事件、权限撤回、故障中断和复核恢复 | 无漏扫/漏阻断/过早恢复；重放幂等；影响扫描与知识修订进度保持独立 |
| `aiot-wifi-knowledge/governance/templates/maintenance-event.json` | F | 复用事件字段并填写旧/新身份与影响理由 | 重放同一事件不重复影响、不重复建卡 |
| `aiot-wifi-knowledge/logs/maintenance/events.jsonl` | R | 受信执行器追加有序事件、影响 Claim 和阻断/恢复记录 | 删除派生索引后仍能重建阻断；事件幂等且不丢待审项 |
| `aiot-wifi-knowledge/logs/maintenance/watermarks.json` | R | 受控写锁下与事件完成状态协调保存 | 中途失败不越过未完成事件，新代激活后才推进应用进度 |

完整职责与约束字段见 ../../traceability.json，同一路径只有一个主模块。F 为固定实现，D/R/X 是实例、产物或外部入口，P 首发延期；不得手造不存在的业务工程或成功证据。
