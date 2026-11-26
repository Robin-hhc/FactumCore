# hs-knowledge-setup（准备知识库执行环境）

## 中文介绍

检查指定知识根的执行环境，确认 CLI、启动入口和基础依赖是否就绪。发现缺项时在用户授权下补齐，环境就绪后回到原查询、入库或巡检任务。

## 使用方式

> 请用 hs-knowledge-setup 检查当前 WiFi 知识库，得到我的授权后补齐缺少的运行组件。

也可直接发起查询、入库或巡检。业务 Skill 确认缺少 CLI、启动入口或运行依赖时，会转到本 Skill。文档解析、默认 OCR 模型和 LibreOffice 按实际缺项分别准备，也可主动指定能力预装。环境就绪后从原步骤继续。

[执行指引](SKILL.md)包含已确认知识根的检查，以及 Windows Samba 映射通过现有 SSH MCP 在 Linux 对端运行的方法。

## 验证

[对话场景](evals/evals.json)覆盖主动检查、业务自检触发、已就绪以及远端配置和授权缺项。用指定知识根的实际 `doctor` 回执确认 CLI 是否就绪。

从仓库根目录运行安装器的机制测试。

```sh
node --test himate/himate-skills/evals/setup/setup.test.cjs
```

复跑首次安装时，为主动调用和业务触发各建一份一次性执行账户或隔离环境。部署同版 Skill，绑定各自的测试知识根，在 CLI 和模型均缺失时验证基础准备。Linux 本机记录 CLI 搜索及读卡回执。Windows 绑定 Samba 目录时记录 SSH MCP 实际执行端和已有 Knowledge MCP 的读卡回执。基础准备完成后发起文档解析，按实际缺项补齐对应能力并续办。安装后对同一环境以相同能力再次执行 `check` 和 `install`，确认 `status` 为 `ready` 且 `performed` 为空。保留安装日志和业务回执，下一轮使用新的隔离环境。
