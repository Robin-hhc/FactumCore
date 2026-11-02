# 随部署携带的 OCR 模型

`docling-cpu/` 保存当前 CPU 推理流程实际使用的 8 个模型/配置文件，合计 **416,177,665 字节（416.18 MB / 396.90 MiB）**。它包含 Heron 布局、TableFormer accurate 表格结构和 RapidOCR ONNX 检测/识别/方向分类模型；不包含当前未使用的 Heron ONNX、TableFormer fast 或 Hugging Face 缓存。

从已有下载并经过 OCR 验证的模型集中复制而来，没有重新下载相同权重。`manifest.json` 记录文件相对路径、大小、SHA-256、来源及可取得的来源 revision。原始下载时的模型说明保存在 `source-cards/`，与运行所需的 8 个文件分开。

部署时优先复用 `artifacts/models/docling-cpu/` 中已有的完整模型；否则验证随包清单和所有文件，复制到上述运行目录后使用。随包模型损坏时明确报错，不自动联网掩盖问题。只有随包模型目录没有携带、且显式指定 `--download-models` / `-DownloadModels` 时才从上游下载。

这些大文件保存在当前工作区，但不通过普通 Git 提交。拷贝部署包时必须同时携带 `models/docling-cpu/` 和 `models/manifest.json`；只克隆源码仓会取得清单与说明，不会自动取得权重。

来源：

- [Heron 布局模型](https://huggingface.co/docling-project/docling-layout-heron)，保留下载时 Apache-2.0 模型卡。
- [Docling TableFormer](https://huggingface.co/docling-project/docling-models)，保留下载时 CDLA-Permissive-2.0 模型卡。
- RapidOCR 3.10.0 的 ModelScope `RapidAI/RapidOCR` ONNX 权重，下载位置与版本记在清单中。[RapidOCR 上游代码许可](https://github.com/RapidAI/RapidOCR/blob/v3.10.0/LICENSE)是代码许可记录，不替代权重来源的条款。

固定 SHA 标识这套已携带资产。运行时仍由 Agent 判断识别内容与图意，文件完整性校验不代替知识内容审阅。