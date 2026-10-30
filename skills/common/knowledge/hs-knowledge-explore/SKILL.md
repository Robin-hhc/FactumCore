---
name: hs-knowledge-explore
description: 知识库任务入口，用于选择入库、查询、检查或巡检能力，以及按需定位项目、准备执行环境和代码图谱。
---

# 选择知识库任务

识别用户目标，复用已有项目与执行端上下文，交给对应能力继续完成任务。

## 任务路由

| 目标 | 使用入口 |
|---|---|
| 新文档入库、增量更新、修改已有卡 | `hs-knowledge-ingest` Workflow |
| 查知识、分析问题、沿证据定位实现 | `hs-knowledge-query` |
| 独立检查正式库或审阅候选 | `hs-knowledge-review` |
| 扫描未入库文档与登记代码变更并处理 | `hs-knowledge-lint` Workflow；周期由外部调度 |
| 明确目标的备料、捕获或原版恢复 | `hs-knowledge-source` |
| 转写本批已定处置为待发布记录 | `hs-knowledge-record` |
| 发布、补检索收尾、索引维护或事务恢复 | `hs-knowledge-apply`，只执行请求的动作 |
| 独立引用审计或维护来源限制 | `hs-knowledge-maintain` |
| 查看某次执行停点 | `python K/knowledge.py status <操作ID> --json` |

review Skill 负责审阅与质量检查；lint Workflow 负责增量治理，四个巡检节点各用自己的指令包。读取所选能力的实际说明；路由成功尚不表示业务完成。

## 定位执行入口

已有有效的项目、知识根 `K` 和执行端信息时直接使用，不重复发现或部署。缺少信息才读[发现接口](references/public-api.md)并运行 `python K/knowledge.py explore`。

项目根的 `config.yml` 指定 K；`code_root` 相对配置目录，模块 `path` 相对代码根。读取实际项目与 K 的 `AGENTS.md`，再按任务补充所需规则。位置不能从 K 的父目录猜测。

命令在数据所在端执行。在 K 内可用 Windows 的 `.\knowledge.cmd` 或 POSIX 的 `sh ./knowledge.sh`；已注册入口时可用 `knowledge`。远端使用宿主已配置的 SSH 工具和服务器原生 K，先取得实际路径，不从映射盘盘符猜远端地址。环境缺项按下节处理。

## 按需准备

- 首次部署、依赖缺项或 dbox 未配置：读[部署与执行](references/setup.md)。日常任务不自动重装或重配。
- 首次初始化或用户要求补齐代码图谱：读[CodeGraph 准备](references/codegraph.md)。查询不因图谱缺失而自行初始化。
- 查看操作进度只读实际状态；续办或修订按目标能力选择，不搜索旧稿猜测本轮意图。

## 交付

报告已选任务、实际执行结果、关键文件引用和剩余缺口。只做发现时交付项目上下文；业务任务已获授权且条件具备时，继续对应任务。Git 提交、CI 和合入按实际授权与结果分别说明。
