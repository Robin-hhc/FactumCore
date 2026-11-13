# FactumCore 测试分支样本

`test` 分支从产品主干 `main` 同步框架代码，并保留用于验收的源码、文档原件和正式知识卡。这里的 `main/` 是测试源码目录。

## 样本范围

- `hi1102_device/`：147 个源码及构建描述文件。
- `hi1105_host/`：442 个源码及构建描述文件。
- [正式知识](../himate/himate-knowledge-wifi-mp/knowledge/index.md)：7 张已生成卡，保留原 ID、正文、定位和旧格式字段。
- [来源登记](../himate/himate-knowledge-wifi-mp/governance/sources.lock.yaml)：仅保留这 7 卡依赖的 10 个来源，含 6 份文档原件及 4 个代码文件；来源 ID、已处理 hash 和时间不变。
- [架构映射](../himate/himate-knowledge-wifi-mp/config.yml)：使用仓内相对路径，可直接定位两套源码。

不包含本机环境配置、派生 SQLite、入库暂存、模型运行缓存或历史测试产物。开发回归源码仍正常保留在 `evals/`。

源码是静态分析样本，现有构建文件依赖树外 kernel/platform，未验证独立编译或硬件运行。原文件主要使用 GB18030；`.gitattributes` 禁止文本归一化，避免改变字节 hash 与定位。来源登记的 `source_commit: null` 保持原值；本分支提交 SHA 标识整套样本版本。

## 开始适配

```sh
git clone --single-branch --branch test https://github.com/Robin-hhc/FactumCore.git FactumCore-test
cd FactumCore-test
```

使用已有 Python 3.10–3.12 和[项目运行依赖](../himate/himate-knowledge-wifi-mp/runtime/requirements.lock.txt)。部署操作参考[使用说明](../himate/himate-knowledge-wifi-mp/docs-llm-wiki/使用说明.md)，使用本分支知识根的 `config.yml`，其中 `code_root: ../../main` 指向本目录。

每轮验收先把远端 `main` 合入 `test`，再在本地测试检出执行 `git pull --ff-only origin test`。从固定提交建立独立试运行副本后执行以下命令。

```sh
python -B himate/himate-knowledge-wifi-mp/knowledge.py maintain reindex --json
python -B himate/himate-knowledge-wifi-mp/knowledge.py source list --json
python -B himate/himate-knowledge-wifi-mp/knowledge.py search "mac_set_snap" --json
python -B himate/himate-knowledge-wifi-mp/knowledge.py read wifi-snap-encapsulation-static --json
```

当前基线预期有 7 张卡和 10 个来源。`mac_set_snap` 能找到静态封装分析卡。索引和查询报告留在试运行副本。验收通过的样本新增或更新可在 `test` 单独提交，业务资料和本机产物留在本机。

面板方案、现有数据与拟议接口见[OpenFlow 面板与知识图谱适配建议](../himate/himate-knowledge-wifi-mp/docs-llm-wiki/OpenFlow面板与知识图谱适配建议.md)。知识内容、代码定位、机械检查和宿主 UI 验收分别判断；本样本不将它们等同。
