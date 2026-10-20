# 当前文档平铺与旧资料仓外归档

日期：2026-10-20。用户要求先 git pull，保留设计目录当前四份文档并平铺至 docs-llm-wiki 根，保留当前 SDD，其他旧文档删除或移出 Git 仓。

## 拉取与最终布局

从 `e0b6bf7e6142d4b15e8f56b6f751aaa099d3bc69` 执行 `git pull --ff-only origin main` 到 `fde520c6a29488401a197e2bc414b4e31283d144`，接收用户七个提交：删除六份旧设计稿，将 aibot.md 改名为 AIoTBot知识库架构.md；没有恢复用户删除稿。

```text
docs-llm-wiki/
├── AGENTS.md
├── README.md
├── AIoTBot知识库架构.md
├── 知识库详细设计.md
└── sdd/
    └── knowledge-v1/
```

四个文件在平铺时逐一验证原字节；随后仅更新入口和必要链接。主设计原字节完全不变，详设四张图逐字不变，需求、阶段表和业务约束不重构。新的 AGENTS 与 README 收口当前入口；仓根导航与 attributes 同步新路径，当前 SDD 引用新名称。历史记录和 baseline 的 previous_sources/旧 amendments 保留原路径身份；148项领域目标文件布局不随本次系统文档整理改动。

## 仓外留存

归档标识：`docs-cleanup-20261020-140445`。本机归档目录在 FactumCore 同级的 FactumCore-archive 下，不加入本仓；归档保留用户未提交研究修改和未跟踪资料。

- 拉取前 `before-pull/` 完整快照144文件，逐文件 SHA-256 核对；其清单摘要为 `0994899541ba2b00fda79c77f782caece3d65a7da5dcd05b2eb0cd718e2f8cce`。
- `retired/` 保存 agents（2）、experiments（3）、research（28）、superpowers（8）、workflows（2）及旧 docs 根 AGENTS（1），共44文件；均与拉取前快照摘要一致。原空设计目录也移出工作区，不保留旧目录导航。
- 归档44文件完整清单位于仓外 `retired-manifest.json`，SHA-256：`f121e40e1f83fbf51541a26056fde11adbc9d0b4e64b1666b3b97c2c65504010`。不把旧研究内容重新纳入当前设计或知识正文。

详设附录A此前引用的实现复核记录原路径为 `docs-llm-wiki/research/aiotbot-knowledge-feasibility-and-detailed-design-2026-10-18.md`，对应归档 `retired/research/aiotbot-knowledge-feasibility-and-detailed-design-2026-10-18.md`，SHA-256：`613404730f5c02368a35ded5690a3837d3b4fedd688b0fd86f5452cf26b4ab91`。它继续代表当时对 CANNBot 固定上游 commit 的静态源码复核，本次未重新安装、运行或评测，也不将未提交归档字节冒充原 Git blob。

## 设计身份与验证

| 来源迁移 | 修改前 SHA-256 | 当前 SHA-256 |
|---|---|---|
| `docs-llm-wiki/设计文档/aibot.md` → `docs-llm-wiki/AIoTBot知识库架构.md` | `b8ff5bf206f021538a2b8e64d7c43a50fcd4ec5bcd60b5fa4b44de464f6e25e0` | `b8ff5bf206f021538a2b8e64d7c43a50fcd4ec5bcd60b5fa4b44de464f6e25e0` |
| `docs-llm-wiki/设计文档/知识库详细设计.md` → `docs-llm-wiki/知识库详细设计.md` | `f71743e47acb460b6c94be5cef68a4a065347e643f3f8038ed4d8e3fd9c75753` | `60b3a73b71bc6f40713d048aede14dd0dfad42863efec5df7f060ab8cddec72d` |

当前 baseline.sources、traceability.source、requirements显式摘要和 attributes 同步当前两份设计；旧 agents 的支持入口改为保留的 SDD tasks/design。取消实际上不存在的领域 .gitattributes 重复支持指针，由仓根属性文件统一维护规则，所有当前 support_files 均可定位。18需求、9模块、28任务、148路径、34验收、49依赖及已有状态/证据引用不变；182个来源行号仍指向各自同一表行。现有 SDD 保留，因为 validator、任务开发与实际验收依赖它。

最终自检通过：根目录精确四文件加sdd；72份活跃Markdown中的166个本地链接均可定位；44文件归档摘要一致；182行号、原图/主设计、共享程序和历史记录字节验证通过。`tools/validate_sdd.py` 返回 `status=ok`：18需求、9模块、28任务、148路径、34验收、49依赖边、3延期项；按原换行策略的范围 diff 检查通过。独立只读审查发现的旧支持指针已修正。

文档整理不增加业务功能，不改写既有测试成绩；未运行的宿主、六Target及权限验收保持原状态。实际发布身份以包含本记录的 Git 提交及远端 main 为准。
