# 知识库任务入口

本页汇总现行设计、实现与验证入口。详细需求、任务、验收和历史记录集中在 [knowledge-v3](sdd/knowledge-v3/README.md)；日常操作见[使用说明](使用说明.md)。

## 现行约定

| 内容 | 依据 |
|---|---|
| 根目录放 AGENTS/config、skills/workflows，知识根保存原件、知识和治理 | [目录架构](AIoTBot知识库架构设计.md#53-aiotbot-knowledge目录架构)、[布局验证](sdd/knowledge-v3/capability-root-layout.md) |
| 一条 ingest 完成 P1—P7，lint 为可复用只读 Skill | [流程与节点设计](知识库详细设计.md) |
| 本地入库、索引和目标查询通过后结束，人工提交／固定 CI／合入随后进行 | [本地完成边界](sdd/knowledge-v3/local-ingest-boundary.md) |
| 代码内容由独立 Agent 复核，固定脚本核对记录及绑定；纯文档保留真人确认 | [内容复核约定](sdd/knowledge-v3/agent-content-review.md) |

## 实现与验证

当前提供 20 个 Skill 和 1 条 ingest Workflow。目录迁移后的完整机制回归为 379 通过、1 跳过，见[布局验证记录](sdd/knowledge-v3/records/capability-root-layout-20261026.json)。真实历史代码、协议候选及增量治理试验另见[扩展语料验证](sdd/knowledge-v3/expanded-corpus-trial.md)，两类证据不合并为全系统准确率。

当前待办按实际范围区分：

| 事项 | 处理方式 |
|---|---|
| 完整背景返回、来源批次复用和轻量输出 | [调整设计](sdd/knowledge-v3/background-retrieval-design.md)待确认；当前仅已补查询 Skill 的回源指引 |
| 内部 Agent 的命令、工作流及真人确认接入 | 在目标部署环境验证，仓内安装和 loader 结果不代替真实接入 |
| 真实业务仓、六 Target／三 pair、宏与构建信息 | 按实际配置和证据补齐，未知项继续保持 unknown |
| 内部 CI、共享接纳与访问控制 | 按真实环境分别验证；固定 CI 复用已有确定性检查 |

## 历史记录

原顶层任务全文按原字节保存在 [2026-10-21 任务记录](sdd/knowledge-v2/records/task-entry-20261021.md)。其中节点数量、旧 Workflow、签名门槛、路径、任务状态和成绩按当时版本解释；原文的相对引用以原 `docs-llm-wiki/` 位置为基准，不作为现行实施清单。
