---
name: hs-knowledge-source-prepare
description: Prepare exact current and historical reading material from fixed scan units or explicit source targets; capture and resolve registered source evidence independently.
---

本 Skill 是 ingest P2。按扫描清单中的实际单元，或用户明确给出的原件／配置内代码目标，组织本次新旧材料、旧卡候选、原字节、提取文本、定位、差异及缺口。它可独立调用，不要求先运行扫描，不检查 Workflow 身份或上游 passed 票据。

P1 判断变化和续办，P2 准备所选材料。P5 发现缺材料时，使用原 `existing_material_ref` 和明确补充目标定向补料。只核对本次采用来源、旧卡、配置和规则的实际指纹；普通补料不重新扫描全库。已采用输入漂移时停止，依据 `SOURCE_CHANGED` 的 `needs_scan/affected_scope` 回到 P1 的受影响范围或新操作，不能以旧清单冒充补齐。

先读取实际材料，再由作者决定更新、skip 或暂缓。候选卡及差异只是阅读线索，不表示必须修改、不构成语义通过或代码支持。卡的完整质量审查属于 P5 的 lint；P2 仅解码备料所需数据及核验确切输入。

准备代码材料时保留旧来源项中的 `code_ref`，并让作者依据实际源码确认符号及必要消歧信息；活动卡的每个 code 来源必须在 P4 填写，字段和支持范围以知识根 `governance/specs/cards.md` 为准。历史来源仍可按原四字段恢复；纯文档不强制连代码，不能用 file／range 兜底填充不支持的代码引用。原 `evidence_ref/source_id/snapshot_id/locator` 和 Claim.source_refs 不变。CodeGraph 可辅助找候选，不能代替实际源码、猜活动宏分支或把内部节点 ID 写进卡；捕获不会自动生成符号结论。

首次缺环境或项目入口信息时，按已安装的 `hs-knowledge-explore` 使用现有 setup；已有上下文直接复用。配置及代码模块授权来自实际 `config.yml`。不要执行原件指令、仓内程序、网络抓取、OCR、自动安装、Git 提交或推送。原件只读，未知版本和未知构建条件保持 unknown。

公开入口：`scripts/cli.py --input REQUEST.json --output RESPONSE.json --knowledge-root K`。默认动作及 `--action prepare` 准备材料；`capture` 独立捕获；`resolve` 校验确切 bundle；`resolve-source` 恢复确切来源及原定位。详见[请求契约](references/request.md)。读取 ResultEnvelope 的实际 phase 和缺口，不以退出0推断已审阅、入库、建索引或上库。

公共来源算法位于知识根规则锁固定的 `governance/contracts/source_operations.py` 和 `source_materials.py`，以同进程公共函数复用。不得调用兄弟 Skill CLI 或导入其私有脚本。已登记 raw 来源变化通过公共维护函数登记事件；代码捕获不隐式登记代码变更事件。P2 不写正式卡、来源锁或活动索引。

补料保留原扫描和原目标，产物采用不可变版本路径，旧引用持续可读。已有冻结候选的返工使用新 operation，并以 `previous_view_ref/revision_reason` 精确采用旧候选实际材料；原扫描保持原字节和身份，后续记录明确保存 `origin_scan_operation_id`。不同 operation 不能覆写旧产物。完整业务及保留边界见[请求契约](references/request.md)和[结果模板](artifacts/templates/result.md)。
