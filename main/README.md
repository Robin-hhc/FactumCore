# FactumCore 测试分支样本

这里的 `main/` 保存配套测试源码。验收同时使用样本文档、正式知识卡和对应来源登记。参见[分支约定](../AGENTS.md#分支约定)。

## 样本范围

- `hi1102_device/`：147 个源码及构建描述文件。
- `hi1105_host/`：442 个源码及构建描述文件。
- 已入库的测试卡保留卡 ID、正文和引用位置。[正式知识](../himate/himate-knowledge-wifi-mp/knowledge/index.md)
- 样本的来源 ID、处理版本和引用定位随分支保存。[来源登记](../himate/himate-knowledge-wifi-mp/governance/sources.lock.yaml)
- [架构映射](../himate/himate-knowledge-wifi-mp/config.yml)：使用仓内相对路径，可直接定位两套源码。

不包含本机环境配置、派生 SQLite、入库暂存、模型运行缓存或历史测试产物。开发回归源码仍正常保留在 `evals/`。

源码是静态分析样本，现有构建文件依赖树外 kernel/platform，未验证独立编译或硬件运行。原文件主要使用 GB18030；`.gitattributes` 禁止文本归一化，避免改变字节 hash 与定位。来源登记的 `source_commit: null` 保持原值；本分支提交 SHA 标识整套样本版本。

## 本地验证

```sh
git clone --single-branch --branch test https://github.com/Robin-hhc/FactumCore.git FactumCore-test
cd FactumCore-test
```

安装本分支对应的工具包和能力包。在 OpenFlow 绑定本检出的 `himate/himate-knowledge-wifi-mp/`，执行环境检查和刷新，即可查看样本卡片及图谱。`config.yml` 的 `code_root: ../../main` 指向本目录。[使用指南](../himate/himate-knowledge-wifi-mp/docs-llm-wiki/HiMate知识库使用指南.md)

在检出根目录用已安装的 CLI 检查样本。本地检出更新步骤见[开发与验收流程](../AGENTS.md#开发与验收流程)。

```sh
knowledge --knowledge-root himate/himate-knowledge-wifi-mp maintain reindex --json
knowledge --knowledge-root himate/himate-knowledge-wifi-mp source list --json
knowledge --knowledge-root himate/himate-knowledge-wifi-mp search "mac_set_snap" --json
knowledge --knowledge-root himate/himate-knowledge-wifi-mp read wifi-snap-encapsulation-static --json
```

`mac_set_snap` 能找到静态封装分析卡。索引和查询报告留在本地测试检出。

面板方案、现有数据与拟议接口见[OpenFlow 面板与知识图谱适配建议](../himate/himate-knowledge-wifi-mp/docs-llm-wiki/OpenFlow面板与知识图谱适配建议.md)。知识内容、代码定位、机械检查和宿主 UI 验收分别判断；本样本不将它们等同。
