# T01 开发记录：声明契约与 CLI

状态：已实现，最终结果由 first-batch-verification.json 及独立审查记录确认。范围是 ticket T01/first-slice 的基础切片，不关闭整套 I0、E01/E02、卡片语义或来源真实性验收。

## 行为与实现

公开 CLI 支持 `contract validate --kind workspace|card|sources|record`。共享程序以安全且拒绝重复键的 YAML/JSON 加载输入，加载本地框架锁和六份固定摘要的声明资产，校验版本、规则字节和 Schema 自身合法性，拒绝远端 $ref 及真实路径绕出，不运行领域 Python 插件。输出统一 JSON 信封和退出码，输入前后摘要不变。

workspace 除 Schema 形状外，检查六个 WiFi Target 唯一身份、repo/领域引用与三组同芯片 Host/Device pair。声明条件逐组 AND、组间 OR；缺失为 unknown，不混组生成新范围。匹配结果不代表 current 断言已有证明。默认配置的业务代码根与构建尚未知，CLI 明确 business_ready=false。

七 Profile、SourceResource/Snapshot 与九类 record 声明只管形状。人工文档声明不要求代码 pass，synthetic 人工记录仅用于测试字段，不伪造任何真实人动作；当前没有写业务卡、实际确认或门禁报告。

## Red 与修正

先编写公共 CLI 的合法配置验收，观察入口尚不存在导致行为失败；原始结果在 T01-red.txt。前两次运行遇到系统 pytest 临时目录权限、专用目录父级缺失，均是环境故障，不计作功能 red。修正测试环境后再记录实际功能失败。

依次补配置反例、损坏规则、远端引用、越界规则、畸形/重复 YAML、七 Profile、纯文档确认记录和 import 无文件写入等用例，针对实际失败实现。首轮合成配置缺少规范要求的 expected_identity，修正 fixture 为显式 null；没有放宽 Schema 迎合测试。T02 公开 CLI 联调又复现 Windows 管道默认编码问题，CLI 已统一 UTF-8 输出并保留真实中文路径回归。

## 可复现与字节策略

使用独立 .venv（Python 3.12.14）；直接依赖与已验证传递依赖分别固定在 requirements-dev.txt 和 requirements-dev.lock.txt。两仓 .gitattributes 固定文本 LF；归一化实际规则文件后重新计算 framework.lock 六项原字节摘要，避免 checkout 换行导致假失配。

git baseline 为框架 `8e538be14542f2180b649ed06629fc80902f0850`，领域 `9ade7f0313fe3ba829e55f56fce50b053ef659a2`。两个基线只是开发边界与工程配置，不是源码、知识或完整首版实现。原 FactumCore 和旧 aiot-knowledge 未被迁移或覆盖。
