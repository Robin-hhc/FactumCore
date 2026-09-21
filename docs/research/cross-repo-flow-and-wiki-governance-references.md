# 跨仓 flow 与 Wiki 治理：成熟实践参考

日期：2026-09-21。状态：公开资料核查与项目适配说明。对应 [总架构设计](../架构设计) §3.3、§3.4。

## 1. 本项目采用的机制

跨仓主要依靠 concepts 内的 flow，结合仓/模块路由、术语映射、卡内来源和各仓代码查询完成。flow 保存跨侧衔接的解释与证据，路由定位下一仓，代码索引帮助展开仓内关系。沿用现有双图谱架构及 AIoTBot 的 raw0/raw1 约定。

治理沿用现有 lint/workflow，区分结构与锚点检查、来源变化后的内容复查。以下公开实践支持这些原则，不要求新增通信契约数据库、统一图或专门状态机。

## 2. 证据概览

| 来源 | 来源类型与观察对象 | 可借鉴机制 | 证据限制 |
|---|---|---|---|
| Linux rpmsg | Linux 内核官方跨处理器通信框架文档 | 消息通道、地址与接收回调建立关联 | 不是知识库方案；不代表本项目使用 rpmsg |
| CodeQL | GitHub 官方 C/C++ 查询指南 | 普通调用与函数指针引用需分别检查 | 不是 CodeGraph 能力测试；不证明必须换工具 |
| Chromium IfThisThenThat | 官方 Gerrit lint 使用指南 | 源块改变时检查关联文件/块是否同步处理 | 检查共同变更，不证明内容语义一致 |
| Karpathy LLM Wiki | 作者原始方法说明 | lint 包含矛盾、过时断言和知识缺口检查 | 不是成熟产品的性能实验，也不是固定实现规范 |

本轮没有运行对照实验，上述来源均不提供本项目准确率、Token、延迟或维护成本的增量数据。它们支撑机制选择，不能证明某个字段设计或自动化程度最优。

## 3. 跨仓：Linux rpmsg 的消息关联机制

[Linux 官方文档：Remote Processor Messaging Framework](https://docs.kernel.org/staging/rpmsg.html)，定位 Introduction、rpmsg_create_ept、register_rpmsg_driver。

**公开事实**：rpmsg 通道以名称及源/目标地址识别；接收回调与本地地址绑定；接收消息时，框架依据目标地址选择处理回调。文档还提供发送和回调注册示例。

**项目适配**：借鉴其显式关联通信两端的方式。Host/Device 的 flow 卡记录实际协议中的消息或事件标识、发送入口、分发/注册/接收入口以及适用条件，sources 指向证据。Agent 读 flow 后利用 config.yml 路由切换代码仓，继续查询实现。

```text
业务问题 → concept-flow → 跨侧消息与处理入口的来源证据
                         → 仓/模块路由 → 对应仓代码查询 → 核验结论
```

无需按函数生成完整流水账；只保留解释流程和跨越边界所需的关键入口。按项目实际协议记录，不照搬 rpmsg 的地址字段。仓路径负责定位；两端为何关联由 flow 与来源解释。

## 4. OPS：CodeQL 对函数指针的处理提醒

[GitHub 官方指南：Functions in C and C++](https://codeql.github.com/docs/codeql-language-guides/functions-in-cpp/#finding-functions-that-are-not-called)，定位 Finding functions that are not called、Excluding functions that are referenced with a function pointer。

**公开事实**：教程先查询没有 FunctionCall 指向的函数，再指出其中仍有间接使用的函数；示例通过 FunctionAccess 检查函数指针引用，进一步缩小候选范围。

**项目适配**：代码查询返回 caller = 0 时，Agent 可沿 concept-flow-ops-dispatch 中的入口核对赋值、注册、触发点与选择条件。flow 提供持续积累的解释和证据，不能单凭没有普通调用边断言函数未使用。无法确定最终实现时保留候选。

这条实践说明应理解查询结果的语义边界，不构成 CodeGraph 或其他索引工具失败的实测证据。

## 5. 变更关联：Chromium 的 IfChange / ThenChange

[Chromium 官方指南：How to use Gerrit IfThisThenThat Lint to keep files in sync](https://www.chromium.org/chromium-os/developer-library/guides/development/keep-files-in-sync/)，定位开头说明与 Syntax。

**公开事实**：LINT.IfChange 和 LINT.ThenChange 可以指定关联文件或文本块。源块改变、对应目标未改变时，lint 在 Gerrit 产生提醒。官方明确这一机制不能替代测试或基本 DRY 原则。

**项目适配**：采用“来源变化就检查关联知识”的维护思路。先用卡内 sources、flow 与模块路由找到相关卡片，交给现有 workflow 复查；不要求向继承源码插入注释，也不要求立即实现精确的依赖图。

关联提醒与语义复查是两个步骤：即使代码和卡片同时修改，也仍需判断更新后的描述是否正确。Chromium 文档不证明自动语义复核已经解决。

## 6. 知识维护：Karpathy 的 LLM Wiki lint

[Karpathy 原始 LLM Wiki 说明](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)，定位 Operations / Lint。

**原文主张**：定期检查页面矛盾、被新来源取代的旧断言、孤立页、缺失引用和知识缺口。这里的 lint 包含知识健康检查，范围超出格式与链接存在性。

**项目适配**：脚本负责结构与锚点，Agent 对照变更来源复查结论、适用条件和冲突。函数仍存在，并不意味着相关业务解释仍适用；只刷新行号不能视为完成内容更新。

作者给出的是可定制方法，不要求特定的 needs_review 枚举、每页人工审批或新的索引系统。本项目先使用待复查标记，对自动流程无法裁决的歧义交由维护者处理。

## 7. 纳入总设计的最低治理要求

1. **触发**：代码合入、构建配置、spec 或原始资料更新，均检查相关知识。
2. **范围**：除卡内直接引用，还考虑公共头文件、宏、消息字段及 OPS 注册等影响；定位不精确时扩大到相关模块并记录不确定性。
3. **复查**：分别检查引用有效性与内容适用性，保留来源版本、条件和冲突。
4. **结果**：仍成立则记录新核验版本；变化则修订；未解决则标注受影响结论待复查，查询时回来源取证；确认被取代后再 deprecated。
5. **验证**：选取一个函数锚点保持有效而行为条件变化的用例，确认相关卡片能够被发现和复查。实际效果及维护成本需在落地中记录。

本节为项目采用的工程要求；上述公开来源提供机制依据，不提供其在 WiFi MAC 工作负载上已经有效的实验结论。