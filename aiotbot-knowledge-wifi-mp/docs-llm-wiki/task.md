# 知识库任务入口

本页汇总现行设计、实现与验证入口。详细需求、任务、验收和历史记录集中在 [knowledge-v3](sdd/knowledge-v3/README.md)；日常操作见[使用说明](使用说明.md)。

## 现行约定

| 内容 | 依据 |
|---|---|
| 根目录放 AGENTS/config、skills/workflows，知识根保存原件、知识和治理 | [目录架构](AIoTBot知识库架构设计.md#53-aiotbot-knowledge目录架构)、[布局验证](sdd/knowledge-v3/capability-root-layout.md) |
| 一条 ingest 完成 P1—P7，lint 为可复用只读 Skill | [流程与节点设计](知识库详细设计.md) |
| 本地入库、索引和目标查询通过并激活后结束，人工提交／固定 CI／合入随后进行 | [本地完成边界](sdd/knowledge-v3/local-ingest-boundary.md) |
| 文档与代码均由独立 Agent 复核，固定脚本核对记录及内容绑定 | [文档自动复核与入库](sdd/knowledge-v3/automatic-document-review.md) |
| 项目配置只维护相对路径和模块归属，工具按路径读取文件并固定内容指纹 | [多仓工作区映射](sdd/knowledge-v3/workspace-mapping.md) |

## 实现与验证

当前提供 18 个 Skill 和 1 条 ingest Workflow，真人确认节点已移除。最近一次[文档自动复核与入库验证](sdd/knowledge-v3/automatic-document-review.md)为 509 通过、1 跳过，包含原件未变时两轮修卡、入库及查询的完整链路；这是隔离机制验证。运行依赖安装、多仓配置分别见[运行环境记录](sdd/knowledge-v3/records/runtime-installation-20261026.json)和[工作区映射](sdd/knowledge-v3/workspace-mapping.md)，各自按对应范围解释。真实历史代码、协议候选及增量治理试验另见[扩展语料验证](sdd/knowledge-v3/expanded-corpus-trial.md)，不将不同范围证据合并为全系统准确率。

当前待办按实际范围区分：

| 事项 | 处理方式 |
|---|---|
| 完整背景返回、来源批次复用和轻量输出 | [调整设计](sdd/knowledge-v3/background-retrieval-design.md)待确认；当前仅已补查询 Skill 的回源指引 |
| 内部 Agent 的命令、工作流及独立复核上下文接入 | 在目标部署环境验证，仓内安装和 loader 结果不代替真实接入 |
| 真实多仓、模块、宏与构建信息 | 配置实际模块路径和归属，工具核对文件内容；公司管理代码视图，标签不证明构建，未知项继续保持 unknown |
| 内部 CI、共享接纳与访问控制 | 按真实环境分别验证；固定 CI 复用已有确定性检查 |

## 历史记录

原顶层任务全文按原字节保存在 [2026-10-21 任务记录](sdd/knowledge-v2/records/task-entry-20261021.md)。其中节点数量、旧 Workflow、签名门槛、路径、任务状态和成绩按当时版本解释；原文的相对引用以原 `docs-llm-wiki/` 位置为基准，不作为现行实施清单。
