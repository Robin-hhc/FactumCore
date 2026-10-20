# 按总体设计 §5.3 整理单仓布局（2026-10-20）

本次按用户最新决定继续在 FactumCore 开发，版本管理的目录以总体设计 §5.3 为准：只接入一个 WiFi 领域，`main/` 为空，四个 Skill、两个 Workflow 暂以 `.gitkeep` 空占位。`.gitkeep` 只让 Git 保存空槽位，不表示能力实现。

```text
FactumCore/
├── AGENTS.md
├── config.yml
├── main/
├── skills/common/knowledge/
│   ├── hs-common-workspace-explore/
│   ├── hs-common-knowledge-ingest/
│   ├── hs-common-knowledge-lint/
│   └── hs-common-knowledge-query/
├── workflows/common/
│   ├── hs-common-knowledge-ingest/
│   └── hs-common-knowledge-lint/
└── aiot-wifi-knowledge/
    ├── docs-raw/
    ├── governance/
    ├── knowledge/
    ├── .build/
    ├── logs/
    ├── docs-llm-wiki/  # 四个平铺文件 + sdd/
    ├── evals/
    └── artifacts/
```

Git 元数据及 `.gitignore/.gitattributes` 作为仓库管理文件保留。`.build/`、`artifacts/` 仅提交空占位，生成内容忽略；已有本地工作树、缓存和其他任务资料不纳入发布。仓根不再保留文档、tools、开发配置或其他领域目录。`docs-raw/sources/` 只保留目录，不创建虚构 URL 或访问能力；首发仍限五类已落地原件。

`docs-llm-wiki/` 从仓根迁到领域目录内；四个平铺文件和 SDD 保留，不再创建“设计文档”子目录。根/领域入口、活跃文档链接、设计摘要与 SDD 当前路径已同步。主设计和详设只修正部署与路径文字，10 个原 Mermaid 图字节保留，原结构和链路未重构；两份设计行数未变，182 个 source_line 锚点无需移位。

## 仓外归档与恢复身份

- 原提交：`ce7b874c7b0ac6fd5549746722055fd928312587`（整理前 main）。
- 仓外归档 ID：`workspace-layout-20261020-142701`，本机位于 FactumCore 的同级 `FactumCore-archive/` 下，不纳入版本库。
- `tracked-before.zip`：完整原提交快照，SHA-256 `cd238396af7f7050252594bea5370944bc60f18e180cb318936eedd7ea5d271f`。
- `retired/`：原共享程序与测试、`tools/`、根 README/CONTEXT/LICENSE、开发依赖/配置及旧 Workflow README，共 29 个原跟踪文件；通过原提交字节或 LF 规范化内容逐个核对。
- `retired-manifest.json`：逐项原路径、归档相对路径、实际字节数和 SHA-256，摘要 `5460f569ff3a7d25865b0c10e9e7745f0ab7658ff4556eadce9fef63535cef8d`。

归档通过移动保留实际工作文件，Git 历史仍保留原实现。若后续恢复，先明确规格、文件落点与恢复范围，再从固定提交或已校验归档提取并重新验证；本次不把它们放入新的 D 盘 clone。

## 当前状态与验收边界

当前部署为 `skeleton_only`，共享 CLI、Skill 和 Workflow 均不可调用。领域已有 Schema、模板、规范及依赖共享程序的契约适配继续保留；适配本身不是独立引擎。新增来源锁为空，未导入真实 raw 或知识卡；缺失的 `check.py/check.sh` 等执行入口仍待 SDD 实现，不放伪成功脚本。

T01/T02/T03/T05/T06/T07 的历史记录及 230 项合成测试成绩保持原身份。`traceability.json` 的既有任务/验收状态表示历史实现进度，`current_deployment` 明确当前可用性；历史通过不等于当前执行部署或真实 WiFi、宿主、权限验收。

本轮只验证目录、链接、摘要、规则锁与 SDD 图一致性，不运行已移出仓库的功能测试来宣称当前能力可用。验证结果见 [workspace-layout-verification.json](workspace-layout-verification.json)。
