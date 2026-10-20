# M03 来源快照：开发设计

## 接口与依赖

| 模块 | 文件 | 对外接口 | 依赖与边界 |
|---|---|---|---|
| M03 来源快照 | `S/sources.py`；`K/governance/sources.lock.yaml`；`K/logs/evidence/`；raw 导航/规范 | `capture_document`、`capture_code`、`resolve_source` 返回 `SourceResource/SourceSnapshot`、恢复对象与 locator；register 返回待应用锁增量 | 依赖 M01 和显式配置身份，编排时接 M02 绑定。原件/源码只读；锁增量进入 final-view；持久包按对象摘要寻址，extract 文本不是新原件入口 |

## 本模块拥有的文件与生成规则

| 路径 | 类别 | 开发动作 | 验收要求 |
|---|---|---|---|
| `skills/common/knowledge/_shared/sources.py` | F | 实现 SourceResource/SourceSnapshot、source resolve/register、document capture；核实际读取字节、附件、编码/提取映射和定位 | dirty/导出/固定 Git 各得真实身份；原件变化可检测；旧版本可恢复；摘要/版本/锚点错误分开诊断 |
| `skills/common/knowledge/_shared/tests/test_sources_scope.py` | F | 构造 raw、附件、代码 dirty/导出、读取中变更和六 Target/三 pair 的合成矩阵 | 真实字节一致性、范围隔离及端到端缺证判断通过；无网页/仓外文档取回 |
| `main/<registered-code-root>/<source-relative-path>` | X | 不在知识项目中新造源码；登记真实根/仓身份/模块边界/ref 或导出政策，再由 sources 按固定快照读取 | 每个已配置 Target 能取回真实快照并定位片段；缺配置如实报 unknown；六 Target 与三配对证据分别验收，不以目录存在代替运行证明 |
| `main/<registered-code-root>/.codegraph/<tool-artifact>` | X | 按实际工具格式生成或接入其产物，随查询结果报告源码快照、构建/Profile、Target、覆盖范围与工具版本 | 旧图/错 Target/宏缺失可识别；每条采用的线索能回到对应源码；有调用边仍须核验注册/宏/跨侧行为，不冒充完整语义证明 |
| `aiot-wifi-knowledge/docs-raw/AGENTS.md` | F | 列允许材料目录、禁止修改原件和人工更新入口 | 指定 sources/网页/越界文件返回 DOCUMENT_SOURCE_DEFERRED，工具轨迹无网络请求 |
| `aiot-wifi-knowledge/docs-raw/index.md` | F | 按材料类列 document_id、已知版本、原件相对路径和来源锁身份 | 每个条目到实际原件及来源身份可解析，缺失明确诊断 |
| `aiot-wifi-knowledge/docs-raw/conventions/<document-id>/<version-or-digest>/<original-file>` | D | 人放入不可变版本目录；生产固定实际字节并提取章节 | 变更能定位到章节；人工确认卡不声称已验证代码遵从 |
| `aiot-wifi-knowledge/docs-raw/conventions/<document-id>/<version-or-digest>/<attachment-file>` | D | 单独登记附件快照并绑定主文档 | 主文不变、附件变化仍能产生影响差异 |
| `aiot-wifi-knowledge/docs-raw/chips/<document-id>/<version-or-digest>/<original-file>` | D | 人放入原件并标注已知 chip/版本，不凭目录补造适用性 | 仅 chip08 资料形成的卡不自动用于其他芯片当前结论 |
| `aiot-wifi-knowledge/docs-raw/chips/<document-id>/<version-or-digest>/<attachment-file>` | D | 为必要附件独立固定摘要和定位 | 附表缺失或读取失败不生成完整成功记录 |
| `aiot-wifi-knowledge/docs-raw/storys/<document-id>/<version-or-digest>/<original-file>` | D | 保留原文及当时环境，提炼时区分经验与已实测归因 | 候选 runbook 显示环境限制、根因状态和未知项 |
| `aiot-wifi-knowledge/docs-raw/storys/<document-id>/<version-or-digest>/<attachment-file>` | D | 逐件绑定快照，保留正文引用关系 | 可从卡片逐项恢复所用附件，缺失形成明确缺口 |
| `aiot-wifi-knowledge/docs-raw/specs/<document-id>/<version-or-digest>/<original-file>` | D | 固定版本，提炼设计断言并标明草案/已批准状态 | 设计意图与代码实现结论可区分，人工确认不冒充代码验证 |
| `aiot-wifi-knowledge/docs-raw/specs/<document-id>/<version-or-digest>/<attachment-file>` | D | 独立登记版本和摘要，建立主文依赖 | 附件修改能定位受影响断言并等待人工再确认 |
| `aiot-wifi-knowledge/docs-raw/protocols/<document-id>/<version-or-digest>/<original-file>` | D | 固定标准版本和适用章节，保留原版分页 | 同一条款跨版本可分别恢复，卡片声明明确标准版本 |
| `aiot-wifi-knowledge/docs-raw/protocols/<document-id>/<version-or-digest>/<attachment-file>` | D | 单独固定快照，记录其对应主版本 | 能同时显示旧条款、勘误和采用决定 |
| `aiot-wifi-knowledge/governance/sources.lock.yaml` | F | 以结构化对象追加快照，卡片按 source_id@snapshot_id 引用 | 从任一卡证据可恢复对应原件；新增快照不改写旧身份 |
| `aiot-wifi-knowledge/governance/specs/sources.md` | F | 解释实际字节、恢复、定位、附件及首发 raw 限制 | 可依据规范登记一份 raw 原件和一个无 Git 代码快照 |
| `aiot-wifi-knowledge/logs/evidence/<bundle_id>/manifest.json` | R | sources.py 捕获/恢复，checks.py 调用生成；登记逻辑源路径、对象摘要、必要版本/格式元数据及提取映射 | 清理 .build 后可恢复所需实际字节；清单与载荷摘要对应 |
| `aiot-wifi-knowledge/logs/evidence/<bundle_id>/objects/<object_digest>.bin` | R | 保存 dirty 文件、无 Git 导出实际文件或可恢复补丁等原字节，按摘要寻址 | 脱离原临时工作区仍能重放准确来源，不拿 HEAD 代替 dirty 字节 |
| `aiot-wifi-knowledge/logs/evidence/<bundle_id>/extractions/<extraction_id>/text.txt` | R | 固定转换器、参数和提取文本摘要，与原字节对象关联 | 可追到原始对象及提取版本，重提取差异可解释 |
| `aiot-wifi-knowledge/logs/evidence/<bundle_id>/extractions/<extraction_id>/locators.json` | R | 保存章节/页码/表图与派生文本区间、相关摘要 | 每个引用可定位回原件，失配映射明确诊断 |
| `aiot-wifi-knowledge/docs-raw/sources/dbox/` | P | 后续接入时登记逻辑对象与本机导出映射；适配器取得固定副本后复用文档确认流程 | 首发请求此类来源返回延期且无网络/卡片写入；未来再验收对象身份、下载/导出和历史恢复 |
| `aiot-wifi-knowledge/docs-raw/sources/wiki/` | P | 后续由授权网页适配器获取正文/必要附件，形成快照与差异 | 首发不发网络请求；未来用固定授权样例验证完整抓取、失效与人工更新 |
| `aiot-wifi-knowledge/docs-raw/sources/3ms/` | P | 保持未支持，取得真实接口与权限条件后另行设计 | 首发返回明确未支持/延期，不建伪造快照 |

完整职责与约束字段见 ../../traceability.json，同一路径只有一个主模块。F 为固定实现，D/R/X 是实例、产物或外部入口，P 首发延期；不得手造不存在的业务工程或成功证据。
