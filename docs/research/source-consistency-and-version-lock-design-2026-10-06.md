# 来源缓存、知识卡与多仓代码的一致性

日期：2026-10-06。状态：源码核对与设计补充；下述来源锁、恢复工具和查询适用性门禁是待实现方案。

## 已核对的现状

所有文档并不都在 `aiot-docs-raw/`。81 份已导入材料在 `docs/` 与 `evals/`；正式卡片在 `knowledge/`；业务代码与真实 SDD 原件随对应工程维护。当前 raw 缓存为空。见 [目录设计](https://github.com/Robin-hhc/aiot-knowledge/blob/main/docs/design_principles.md)、[迁移清单](https://github.com/Robin-hhc/aiot-knowledge/blob/main/docs/migration-manifest.json)。

当前 AIoT 实现检查本地来源的登记根与文件存在性；已识别 Git URL 只检查固定 commit 格式，没有核对实际远端内容、workspace HEAD/dirty/Target。见 [knowledge.py](https://github.com/Robin-hhc/aiot-knowledge/blob/main/governance/contracts/knowledge.py#L158)。SQLite 指纹覆盖 `knowledge/` 和 `governance/`，没有覆盖原文或业务源码；因此同路径的原文换内容不会使当前索引陈旧检查失败。见 [指纹与查询实现](https://github.com/Robin-hhc/aiot-knowledge/blob/main/governance/contracts/knowledge.py#L345)。81 个导入快照的 SHA-256 校验是历史材料保护，不是通用来源锁。见 [check.py](https://github.com/Robin-hhc/aiot-knowledge/blob/main/check.py#L18)。

CANN 核对基于本地固定 checkout `e7c4942d27aa753cf0a98a1a3edf56aa1e4c8c35`，不是对未来版本的保证：

- 源码 Registry 登记仓库与固定 commit，资源恢复后验证 HEAD、origin 和 clean tree。见 [Registry](https://gitcode.com/cann/cannbot-knowledge/blob/e7c4942d27aa753cf0a98a1a3edf56aa1e4c8c35/governance/schemas/registries.yaml#L85)、[源码资源校验](https://gitcode.com/cann/cannbot-knowledge/blob/e7c4942d27aa753cf0a98a1a3edf56aa1e4c8c35/governance/contracts/source_resources.py#L115)。
- 文档资源使用持续更新的归档 URL；`.complete` 检查地址而不锁定文档内容。见 [文档登记](https://gitcode.com/cann/cannbot-knowledge/blob/e7c4942d27aa753cf0a98a1a3edf56aa1e4c8c35/governance/schemas/registries.yaml#L118)、[归档校验](https://gitcode.com/cann/cannbot-knowledge/blob/e7c4942d27aa753cf0a98a1a3edf56aa1e4c8c35/governance/contracts/source_resources.py#L23)。下载脚本复用旧缓存时明确不检查历史 hash，刷新会下载当时最新文档。见 [get_resources.sh](https://gitcode.com/cann/cannbot-knowledge/blob/e7c4942d27aa753cf0a98a1a3edf56aa1e4c8c35/get_resources.sh#L83)。因此同一知识 commit 不足以保证不同时间恢复的文档字节一致。
- mirror verify 可以检查本地文档转换后的知识一致性，但普通 check 不调用完整 mirror verify。见 [mirror verify](https://gitcode.com/cann/cannbot-knowledge/blob/e7c4942d27aa753cf0a98a1a3edf56aa1e4c8c35/.agents/skills/knowledge-ingest/scripts/fixed_archive_docs.py#L1024)、[check.sh](https://gitcode.com/cann/cannbot-knowledge/blob/e7c4942d27aa753cf0a98a1a3edf56aa1e4c8c35/check.sh#L17)。

结论：可以沿用 CANN 的目录职责；多人协作的版本一致性需要比滚动文档缓存更明确的约束。

## 推荐的共享边界

| 资产 | 团队共享与版本控制 | 本地物化 |
|---|---|---|
| 知识卡、治理规则、系统设计 | 知识 Git 仓提交，按知识版本共同审查 | clone 对应知识版本 |
| 自有小型 Markdown 来源、SDD 原件 | 对应业务/文档 Git 仓，以固定 commit 引用 | 读固定 Git 对象或独立快照 |
| 大型 PDF、芯片手册、图像、日志 | 有权限的团队文档库或对象归档保存不可变版本；也可采用 Git LFS | 恢复到 raw 缓存，核对字节 hash |
| 来源身份、版本、hash 与恢复信息 | 拟新增知识仓内 `governance/sources.lock.yaml`，与卡片一起提交 | 按该清单恢复和验证 |
| 转换中间件、检索索引、代码图 | 按输入版本和工具配置生成，可重建 | `.build/`、`artifacts/`、各代码仓 `.codegraph/` |

Git LFS 的官方机制是仓内保存指针、实际大文件由外部存储提供；指针包含内容 SHA-256 与大小。可据此选择大文件的共享方式，但仍需确保团队能恢复旧对象。见 [官方说明](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-git-large-file-storage)。Git 可核验 revision 是否对应实际 commit 对象，不能只接受形似 hash 的字符串。见 [git rev-parse](https://git-scm.com/docs/git-rev-parse)。

不上 Git 的应是可重建缓存，而不是原文唯一副本。若没有可持久取得的上游，先将原件纳入团队受控文档仓/归档，再发布基于它的卡片；仅有个人磁盘路径不满足共享证据条件。

## 来源锁与卡片依据

拟议来源锁每条记录包含 source ID、来源种类、权威仓/归档地址、不可变 revision/对象版本、文件路径、内容 SHA-256/大小、恢复方式和本地缓存落点。凭据通过既有权限体系提供，不写入清单。资料按 `<资料集>/<版本>/...` 恢复，旧快照保留；滚动入口可以用于发现更新，不能代替已发布卡片的固定证据地址。

卡片需要把关键结论绑定到来源条目及版本，并记录代码 repo/commit、适用 Target/芯片/构建条件和复核依据。跨 Host/Device 流程绑定多仓版本组合，不能只写一个全局 revision。现有 `sources` 字符串可继续作为定位入口，但解析器还需把路径/URL关联到来源锁；本文不宣称当前 Schema 已支持新的 source ID 语法。

workspace 的 `config.yml` 管仓身份、路径和路由；来源锁管卡片的固定证据版本；实际各仓 HEAD、修改状态和构建条件用于判断当前问题的适用性。不要把三者都叫“当前版本”，也不要在多处独立维护同一来源的权威版本值。

## 恢复一致性与查询适用性分别处理

**恢复一致性**：同一知识版本引用的同一 source ID，应恢复出相同证据字节。按锁定版本获取、hash 校验通过后，才能作为该卡的核验来源。缺资料或 hash 不符时报告该来源不可用，不能自动接受同名的其他版本。`.complete`、路径存在、修改时间或下载成功本身不足以证明内容相同。

**查询适用性**：历史证据一致，不代表适用于当前代码。查询应比较卡片依据与实际多仓代码、Target 和构建条件；本地修改也要纳入判断，不能仅比较 HEAD。允许读取历史卡作线索，但证据未匹配时不得作为当前已核验事实返回。

| 本地情况 | 建议查询行为 |
|---|---|
| 来源已恢复且 hash 正确，当前代码/条件匹配已复核范围 | 按卡片已验证范围回答并引用版本 |
| 来源未恢复或不可访问 | 标明无法回读所需来源；需要该证据的结论保持未核验 |
| 来源同路径但 hash 不符 | 隔离该缓存并按来源锁恢复；不沿用“已验证”标记 |
| 代码不同 commit、存在相关本地修改或 Target 不匹配 | 标明版本/条件差异，回当前源码取证；必要时提交复核候选 |
| 已有明确证据证明卡片也适用于新的版本 | 采用已记录的新适用范围；不能仅凭文件名、函数名或单文件 hash 相同推断 |

本地版本差异是本次查询的适用性结果，不应直接改坏共享卡的生命周期。同一卡可以仍适用于旧版本；团队采用新来源/代码基线时才走共享复查流程。卡片标为 stable、索引有效、来源字节匹配与技术结论正确分别表达不同性质。

## 更新闭环

1. 策展人或受控流水线发现新的文档/代码版本；保留旧锁与旧快照，新版本作为候选。
2. 根据 source 引用、模块路由和版本差异定位受影响卡。初期扫描卡片即可；公共头文件、宏、构建配置、消息字段等间接影响需一并评估，不要求先建设独立依赖图服务。
3. 记录受影响结论待复查。Agent 对照新旧内容检查结论与条件，而不只是修复路径/行号；不确定时由维护者裁决。
4. 知识 PR 一起审查新的来源锁、卡片修订和复核记录。知识仓内同一次提交发布这些变更；外部代码仓仍独立合入，以明确的多仓版本组合关联，不能声称多仓 Git 合入天然原子。
5. CI 恢复该知识版本需要的来源，检查 hash/commit、结构、引用及对应验证；本地按版本重建知识索引和代码索引。索引仍只是定位工具，不能代替内容复查。

理想消费链路为：`同步知识版本 → 按来源锁恢复 → 校验当前多仓/Target → 查询卡片及证据`。更新链路为：`发现新来源 → 定位受影响卡 → 内容复查 → 卡片+锁共同发布`。

## 实施与验收边界

本轮新增的是设计，没有实现自动恢复、来源内容校验或当前 workspace 适用性门禁。现有 20 项契约测试不覆盖上述完整闭环。后续最小实施顺序是：来源锁和恢复校验；查询前适用性检查；来源变更影响扫描与审查发布。

后续应使用合成测试资料验证：两份同知识版本 checkout 恢复出同 hash；篡改同路径文件会失败；代码 HEAD 相同但有相关 dirty 修改会提示；Host/Device 组合不匹配不宣称已核验；来源更新时函数仍存在但语义改变能进入复查；更新锁与卡片后，两份 checkout 得到同样的版本判定。正式产品效果仍需真实来源与源码验证。
