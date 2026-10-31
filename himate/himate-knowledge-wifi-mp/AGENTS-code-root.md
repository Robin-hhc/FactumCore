# 代码仓开发指引

## 项目概述

...

## 代码架构与模块

...

## 目录说明

| 位置 | 职责 |
|---|---|
| `main/` | 默认业务代码工作区，可含多个实际 Git 仓；未接入真实代码时不创建虚构源码树 |
| `config.yml` | 项目架构映射：代码根、模块相对路径、芯片、Host／Device、特性及用途；工具按路径核对文件与内容指纹 |
| `himate/himate-knowledge-wifi-mp/` | 默认领域根；实际位置由 `config.yml` 的 `knowledge_roots` 指定，原件、契约、知识及本地运行支撑按其 AGENTS 分层 |
| 知识根下的 `skills/`、`workflows/`、`tools/` | 知识能力分发源码、工作流定义及工具，均相对上行的知识根 |
| `himate/himate-knowledge-wifi-mp/docs-llm-wiki/` | 共享架构、概要与详细设计、使用说明；本项目 `sdd/` 与 `task.md` 仅本地维护，不在仓根另建文档目录 |

文档入库使用 `hs-knowledge-ingest` Workflow，巡检使用 `hs-knowledge-lint` Workflow，检索使用 `hs-knowledge-query` Skill，实际命令由知识根内的 `knowledge.py`／`knowledge.cmd`／`knowledge.sh` 执行；用法见该根的共享使用说明。

本项目根是 manifest 工作区根，不要求自身为 Git 仓。Git 历史与提交在文件所属的实际仓操作，多仓同步按配置的 manifest 根执行；日常知识操作通过上述能力执行。

## 构建、运行与测试

...

## 开发规范

...

## 常见开发流程

...
