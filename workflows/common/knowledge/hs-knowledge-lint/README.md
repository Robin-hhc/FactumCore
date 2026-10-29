# WiFi 知识引用巡检 Workflow

此模板由 OpenFlow 直接编排两个已安装 Skill 节点，供手动启动或已有外部调度定期启动。只生成正式库检查及引用差异报告，保留原检查的失败和未完成范围。

目标代码仓在远端时，通过 OpenFlow／宿主已有的 SSH MCP 在远端项目根执行脚本、读取文件和进行仓库操作，使用执行端的全局 Python 与已安装 Skill 路径，并核对实际结果；本地路径不能直接用于远端。连接由宿主管理，Skill／Workflow 不维护单独的 SSH 配置。

1. `check_formal` 调用原 `hs-knowledge-lint` Skill，沿用默认 formal/full。Agent 根据实际项目配置准备确切来源输入及适用的 `inputs.code_checkout`，将原 JSON 报告保存到知识根 `.build/` 内的新路径。
2. `audit_references` 显式调用 `hs-knowledge-maintain --action audit-references`，传入本次 `operation_id` 与相对知识根的 `lint_report_ref`，读取返回的 `audit_ref` JSON 和 `report_ref` Markdown。将实际 `report_ref` 在执行端解析为真实文件路径，显式填入产物实例的 `location.path`，不能以模板默认位置代替报告，再按 `reported` 出口结束。

`workflows/common/knowledge/hs-knowledge-lint/` 是开发分发的 Workflow，安装后位于宿主 Workflow 目录；`skills/common/knowledge/hs-knowledge-lint/` 是同名只读检查 Skill，安装后位于宿主 Skill 目录。两者处于不同资源命名空间。原 `knowledge lint` 逻辑命令仍表示单独调用只读 Skill；巡检需要显式启动本 Workflow。

原 lint 报告为 failed/incomplete 时仍可进入引用汇总；巡检报告有问题或未完整时也可完成“报告生成”。这些状态必须原样披露，不能声称全库健康、已修复或已更新索引。规则或运行错误导致没有可用报告时保留宿主原生等待，不能选择结束出口。

模板不调用子 Workflow，不自动修订、不入库、不登记变化事件或推进水位，不重建或激活活动索引。后续修订由用户另行发起 ingest。文件指纹变化表示引用依据发生变化，Agent 查询时仍须读取当前实际函数及所需周边代码；未引用的代码语义变化不属于本巡检的完整覆盖范围。

`workflow.yaml` 定义节点、角色和出口；`layouts.yaml` 定义画布坐标。源文件和原件保持只读，报告留在知识根已有 `.build/` 体系。当前模板未内置定时器，也不建立外部 runner。

本Workflow仍仅上述两个节点。lint和audit可写本次自己的stage报告，不清理这些报告、不清其它任务stage，也不发布ingest业务内容。常规本批清理只属于ingest P7；独立maintain明确事件／水位动作保持其原业务职责，不因ingest前六步暂存约束而失效。
