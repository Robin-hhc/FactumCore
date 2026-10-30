# 只读项目发现

仅在缺少项目位置或配置上下文时使用。已有有效上下文直接进入业务能力。

```text
python K/knowledge.py explore --input REQUEST.json --json
```

```json
{"operation_id":"discover-project","target_path":"<执行端已存在的项目或代码路径>"}
```

| 输入 | 用途 |
|---|---|
| `target_path` | 必需；实际存在的项目、目录或文件 |
| `config_path` | 可选；明确采用哪份根配置 |
| `target_id` | 可选；选择逻辑芯片/端组合，标签不证明构建或宏状态 |
| `--rules-digest` | 可选；固定本次实际规则摘要 |

成功为 `context_loaded`，返回 `context_ref/context_digest`。读取记录中的项目根、K、模块范围、实际入口说明与缺口，再选择业务能力。找不到唯一配置、实际入口或必要规则时报告诊断，不拿 `.example` 代替实际 `AGENTS.md`。

模块配置使用 `code_root` 和 `modules[].path`；空模块列表可处理文档，但不授权读取全部代码。代码版本、宏、构建和运行条件按实际证据保留未知，不由模块标签推断。发现过程不安装依赖、建库或恢复旧操作。
