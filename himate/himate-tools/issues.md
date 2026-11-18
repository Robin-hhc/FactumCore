# evals 测试问题清单

- 测试环境：Windows 11 Pro 10.0.26100、Python 3.11.4、Node v24.13.1、npm 11.8.0
- 仓库版本：himate-tools 0.24.2（提交 5451d99）
- 全量门禁结果：`8 failed, 451 passed, 12 skipped, 1 error`

---

## Issue 1：Windows 下含内嵌图片的文档解析报 UNSAFE_PATH

**环境**
- Windows 11 Pro 10.0.26100
- Python 3.11.4
- 仓库版本：himate-tools 0.24.2（提交 5451d99）

**复现**

```bash
python -m pytest "evals/contracts/test_document_parser.py::test_real_embedded_images_are_saved_and_bound_to_source[.png]" -q
```

同样失败：`.docx`、`.xlsx`、`.pptx`；`test_two_frame_tiff_explicitly_reports_the_unprocessed_frame`、`test_successful_standard_first_frame_does_not_hide_later_tiff_frames` 也失败，共 6 个。

**实际结果**

```
ContractError: UNSAFE_PATH: Expected a relative POSIX path
(images\image_000000_5f69e00f46ffcf96e6eee7804d54547882b4f9189594f1bf4b68a1b9762f445e.png)
```

**证据**
- 失败点在 `runtime/governance/contracts/document_parser.py:1099`，`load()` 直接取 `document.pictures[].image.uri` 传给 `safe_path(output, uri, ["images"])`。
- 该校验在 `runtime/governance/contracts/validation.py:131` 拒绝含反斜杠的路径。
- 同一用例在 Linux 上未验证。

**推论**
docling 在 Windows 上用 `os.path.join` 生成图片 URI，得到反斜杠形式；代码假定 URI 为 POSIX 相对路径。该问题仅在 Windows 触发，不影响 Linux 解析路径。

**影响**
Windows 本机无法解析含内嵌图片的 docx/xlsx/pptx/png/tiff 文档；纯文本类文档不受影响。

---

## Issue 2：模型安装测试在 Windows 上因路径超长误报文件缺失

**环境**
- Windows 11 Pro 10.0.26100
- Python 3.11.4、Node v24.13.1
- 仓库版本：himate-tools 0.24.2（提交 5451d99）

**复现**

```bash
python -m pytest evals/deploy/test_npm_models.py::test_model_install_joins_parts_and_keeps_cli_and_logs -q
```

稳定失败。

**实际结果**

```
FileNotFoundError: ...\models\docling-cpu\docling-project--docling-models\
model_artifacts\tableformer\accurate\tableformer_accurate.safetensors
```

但同一路径用 `os.listdir` 能看到该文件。

**证据**
- 断言位置：`evals/deploy/test_npm_models.py:79`。
- 失败路径长度为 264 字符，超过 Windows `MAX_PATH` 260。
- 在该路径上 `Path.exists()` 返回 `False`，`os.listdir(parent)` 返回包含该文件名的列表。
- 安装脚本返回码为 0，文件实际已写入。

**推论**
这是 Windows 传统路径长度限制导致的断言误判，不是安装逻辑丢文件。测试临时目录 `pytest-of-.../test_model_install_joins_parts0/user profile/...` 使总长度超过 260；真实安装路径 `~/.himate/knowledge/tools/deploy/models/...` 更短，未触发。

**影响**
仅影响 Windows 下该测试的可信度；Linux 未验证。

---

## Issue 3：npm CLI 启动器测试在 Windows 上 rename 报 EPERM

**环境**
- Windows 11 Pro 10.0.26100
- Python 3.11.4、Node v24.13.1、npm 11.8.0
- 仓库版本：himate-tools 0.24.2（提交 5451d99）

**复现**

```bash
python -m pytest evals/cli/test_npm_cli_launcher.py -q
```

全量运行 `evals/deploy evals/cli evals/contracts` 时出现 1 个 ERROR（`test_npm_cli_propagates_error_status_and_json`）；单独运行该文件时曾出现 2 个 ERROR（`test_npm_cli_uses_path_python_without_creating_an_environment`、`test_npm_cli_reads_selected_pythons_user_site`）。

**实际结果**

```
Error: EPERM: operation not permitted, rename
'C:\Users\...\profile & tools ! 资料\.himate\knowledge\runtime'
```

**证据**
- 报错位置：`evals/cli/test_npm_cli_launcher.py:67` 的 fixture 安装步骤。
- 失败不稳定：同一文件有时 5 passed / 1 skipped / 2 errors，有时仅 1 个 error。
- 临时目录名包含 `&`、`!`、中文等字符。
- 在 Linux 上未验证。

**推论**
Windows 上目录被占用或重命名权限受限时会返回 EPERM；测试临时目录的特殊字符和并发执行可能放大了该现象。目前无法判断是环境偶发还是安装流程在 Windows 上的固有问题。

**影响**
Windows 下启动器测试结果不稳定；不影响 Linux 目标机判定，但会干扰本地全量门禁。

---

## Issue 4：npm upgrade 测试在全量运行时偶发失败

**环境**
- Windows 11 Pro 10.0.26100
- Python 3.11.4、Node v24.13.1
- 仓库版本：himate-tools 0.24.2（提交 5451d99）

**复现**

```bash
python -m pytest evals/deploy evals/cli evals/contracts -q
```

全量运行时 `test_npm_postinstall_preserves_managed_environment_and_logs` 失败；单独运行该用例通过。

**实际结果**
- 全量：`8 failed, 451 passed, 12 skipped, 1 error`
- 单独：`1 passed in 0.21s`

**证据**
- 同一提交、同一环境下，失败无法稳定复现。
- 该用例在 0.24.1 的全量运行中曾通过。
- 本次改动仅涉及 `package.json`、`framework.lock.yaml`、`manifest.json` 的版本号与哈希，未触及该用例逻辑。

**推论**
更可能是全量并发执行时的临时目录竞争、文件占用或测试间状态干扰，而非版本号改动引入的确定性缺陷。由于无法稳定复现，暂不能定位到具体共享资源。

**影响**
本地全量门禁结果不稳定；尚不能确认是否会在 Linux CI 出现。

---

## 补充说明

- 本次 0.24.2 发布门禁为 `8 failed / 451 passed / 12 skipped / 1 error`，其中 6 个 document_parser 失败和 1 个模型安装失败可稳定复现，另 1 个 upgrade 失败与 1 个 launcher error 为偶发。
- 所有失败均在 Windows 本机出现，Linux 侧尚未实跑验证，因此“不影响 Linux”目前是推论而非实测结论。
