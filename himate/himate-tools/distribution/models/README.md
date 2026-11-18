# OCR 模型 npm 包

`docling-cpu/` 保存当前 CPU 推理流程实际使用的模型资产，安装后为 8 个模型/配置文件，合计 **416,177,665 字节（416.18 MB / 396.90 MiB）**。它包含 Heron 布局、TableFormer accurate 表格结构和 RapidOCR ONNX 检测/识别/方向分类模型；不包含当前未使用的 Heron ONNX、TableFormer fast 或 Hugging Face 缓存。

从已有下载并经过 OCR 验证的模型集中复制而来，没有重新下载相同权重。`manifest.json` 记录文件及分片的相对路径、大小、SHA-256、来源及可取得的来源 revision。下载时的模型说明保存在 `source-cards/`（发布副本仅清理行尾空白），与运行所需的 8 个文件分开。

用户通过 `npm install -g @himate/knowledge-models` 安装模型包。安装脚本校验清单、分片和最终文件，合并并准备当前账户的 `~/.himate/knowledge/tools/deploy/models/docling-cpu/` 模型集。standard OCR 未指定模型路径时使用这套本机模型。知识库显式配置 `artifacts/models/` 下的模型目录时，继续使用该配置。

模型资产通过普通 Git 提交。两个超过 100 MiB 的权重拆为不超过 48 MiB 的 `.part001` 等分片，npm 安装时自动校验并合并。发布模型包时保留完整的 `docling-cpu/`、`manifest.json` 和安装脚本。CLI 升级保留已安装模型。

模型来源记录如下。

- [Heron 布局模型](https://huggingface.co/docling-project/docling-layout-heron)，保留下载时 Apache-2.0 模型卡。
- [Docling TableFormer](https://huggingface.co/docling-project/docling-models)，保留下载时 CDLA-Permissive-2.0 模型卡。
- RapidOCR 3.10.0 的 ModelScope `RapidAI/RapidOCR` ONNX 权重，下载位置与版本记在清单中。[RapidOCR 上游代码许可](https://github.com/RapidAI/RapidOCR/blob/v3.10.0/LICENSE)是代码许可记录，不替代权重来源的条款。

固定 SHA 标识这套已携带资产。运行时仍由 Agent 判断识别内容与图意，文件完整性校验不代替知识内容审阅。
