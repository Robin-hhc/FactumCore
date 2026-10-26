# 复制到业务项目根的文件

这里集中保存需要手动放到知识库外层的两个文件：

| 文件 | 放到哪里 | 已写好的内容 |
|---|---|---|
| [AGENTS.md](AGENTS.md) | `<业务项目根>/AGENTS.md` | 知识入口、命令分派、背景与代码回源、入库和检查边界 |
| [config.yml](config.yml) | `<业务项目根>/config.yml` | 知识库路径、同仓代码映射、六逻辑 Target、三 pair 与查询通道 |

```text
<业务项目根>/
├── AGENTS.md
├── config.yml
├── <现有业务代码目录与文件>
└── aiotbot-knowledge-wifi-mp/
    ├── docs-raw/、knowledge/、governance/
    ├── skills/、workflows/
    └── project-root-files/       本目录仅为待复制文件，不是生效位置
```

项目已经有同名文件时，将知识库入口和配置合并进去，保留原项目的开发、构建与测试约定。文件名使用 **`AGENTS.md`**；根目录仅保留一份实际使用的 `config.yml`，不把本目录中的副本当作第二套运行配置。

需要按真实项目补充的内容：

| 配置 | 怎么填写 |
|---|---|
| `workspace_id` | 改成该项目唯一且稳定的标识 |
| `repos[].root` | 默认 `.` 表示复制后 config 所在的业务 Git 仓根；代码分属其他仓根时按实际改，不要求建 `main/` |
| `repos[].expected_identity` | 代码入库核验前填写真实内部仓的 `remote.origin.url`，模板保留 null，不预设地址 |
| `architecture`、`wiki_entities`、`symbol_aliases` | 真实模块、实体和符号已明确后再补映射 |
| `targets`、`pairs` | 六 Target／三 pair 是现有契约的逻辑标识；真实源码绑定、模块目录、宏、构建和兼容关系未知时保持空值或 unknown |
| `code_policy` | 接入代码捕获／核验时，由部署方填写实际代码根授权，并与内部 Agent 受信侧的配置一致；模板不预填机器路径或授权 |

只复制这两个文件会补齐知识入口和基础映射，不会生成代码身份或构建证据。业务代码相关的核验要求仍按真实配置完成。

复制并补齐实际配置后，日常下发命令见[使用说明](../docs-llm-wiki/使用说明.md)。
