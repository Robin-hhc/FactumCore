# 万卡查询与索引验收语料

`perf-10k-v1` 供性能分支使用。输入由固定规则生成，Windows 和 Linux 使用同一提交和 [内容指纹](fixture.json) 验收。

| 内容 | 数量 | 位置 |
| --- | ---: | --- |
| Markdown 源文档 | 1,000 | `himate/himate-knowledge-wifi-mp/docs-raw/specs/perf-10k/` |
| 正式知识卡 | 10,000 | 知识根的各类型目录下的 `perf-10k/` |
| 已登记的 C 代码文件和可引用函数 | 10,000 | `main/perf-10k/` |
| 图谱节点 | 21,000 | 已发布视图 |
| 图谱边 | 30,000 | 原件引用、代码引用和卡片链接各 10,000 |

每份原件对应十张卡。每张卡引用原件的对应行、同一用例的 C 函数及同原件的下一张卡。十个主题、七种卡片类型和固定标签覆盖过滤、分页、高频搜索、精确搜索与邻居展开。`radio` 是高频词，`case10000` 用于定位尾部卡片。

## 核对输入与建立索引

在仓库根运行以下命令。两套环境各自建索引，记录提交、CLI 版本、知识根及运行结果。

```sh
python perf/10k/generate.py verify .
knowledge --version
knowledge doctor --knowledge-root himate/himate-knowledge-wifi-mp --json
knowledge maintain reindex --knowledge-root himate/himate-knowledge-wifi-mp --json
knowledge library overview --knowledge-root himate/himate-knowledge-wifi-mp --json
```

需要独立重建输入时，运行 `python perf/10k/generate.py create <新目录>`，再用 `verify <目录>` 校验。生成器使用 Python 标准库，校验范围包括素材、来源账本、配置和指纹。`knowledge.sqlite` 和预览副本由各宿主重新生成。

用同一提交的独立检出验证首次建库、无改动刷新、单卡增删改、重命名和仅来源变化。各场景记录输入变化及 UI 或 CLI 的耗时。Windows 宿主分别验证 SSH MCP 和 Samba 的代码读取。Linux 宿主从 Windows 浏览器经实际反代访问。

## 分支维护

性能分支从 `main` 获取开发更新。合入后核对素材指纹，给性能报告记录完整提交和语料指纹。常规功能继续用 `test` 的基础样本。
