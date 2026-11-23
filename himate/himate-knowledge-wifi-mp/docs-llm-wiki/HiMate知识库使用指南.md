# HiMate 知识库使用指南

首次使用时，先确认知识库命令在哪台机器执行并部署能力包，再在 OpenFlow 的知识库页校验目录、补齐环境并保存绑定。

## 1. 准备

先确认运行 `knowledge` 的机器和账户。

| 知识库位置 | 命令执行位置 |
|---|---|
| Linux 宿主的本地目录，包括从 Windows 浏览器访问的反代站点 | Linux OpenFlow 启动账户 |
| Windows 宿主的本地目录 | Windows OpenFlow 启动账户 |
| Windows 宿主绑定 Samba 映射盘或共享路径 | OpenFlow 已配置的 SSH MCP 所连接的 Linux 账户 |

在命令执行端准备 Node.js 18 或更新版本、Python 3.10–3.12 和 pip，并确认该端可访问内网 npm 源。

取得项目知识仓和 `himate-skills` 能力包。知识仓内的 `config.yml` 由项目负责人配置，普通使用者使用项目提供的版本。

## 2. 安装 Skills 和 Workflows

在运行 OpenFlow 的机器上进入 `himate-skills` 目录，按操作系统执行对应脚本。

Windows PowerShell。

```powershell
.\deploy.ps1
```

Linux。

```sh
sh ./deploy.sh
```

脚本安装 Agent 使用的操作指引和工作流模板，过程中会询问安装目录。使用默认 OpenFlow 配置时，直接回车即可。完成后会显示安装数量和目标目录。

| 安装内容 | 默认位置 |
|---|---|
| OpenFlow Skills | `~/.openflow/config/skills` |
| CAC Skills | `~/.cac/skills` |
| OpenFlow Workflows | `~/.openflow/config/workflow-templates` |

使用其他目录时，按实际位置填写。能力包位置不同或需要无人值守安装时，参数见能力仓的[安装说明](../../himate-skills/README.md)。

## 3. 打开 OpenFlow 并连接知识库

使用部署能力包的宿主账户启动 OpenFlow。已经打开的 OpenFlow 先重启，让它加载刚安装的能力。

1. 点击左栏「知识库」。首次进入可跟随气泡指向的控件操作。可以跳过，之后通过页头「使用指引」重新打开。
2. 选择项目知识仓的根目录。该目录中应能看到 `config.yml` 和 `docs-raw/`。
3. 点「校验目录」。如果提示缺少 CLI 或依赖，按下一节补齐后回到绑定页。如果 Windows 共享目录提示配置 SSH MCP，打开设置，启用已有的 SSH 连接并添加共享目录到 Linux 目录的路径映射，再返回校验。
4. 校验通过后点「保存绑定」。点页头「环境检查」，确认实际执行端已就绪。

## 4. 在页面检查和安装环境

- 本地目录缺少 `knowledge` 时，打开绑定页的「查看 CLI 安装指引」，也可以从页头「环境检查」进入。在弹窗点「同意并安装」，OpenFlow 会尝试安装模型和 CLI。使用终端安装后可点「重新检查」。如果仍找不到命令，把 npm 全局命令目录加入启动账户的 PATH，再重启 OpenFlow。
- 本地 CLI 已就绪但缺少 Python 依赖时，点「安装环境」。可以看进度或选「后台继续」。后台安装进度显示在知识库页头，完成或需要处理时会出现提示。
- Windows 绑定 Samba 时，缺少 CLI、模型或 Python 依赖，由 SSH 连接使用的 Linux 账户在对端执行下一节命令。安装后确认该 SSH 账户的 PATH 能找到 `knowledge`，再回 OpenFlow 重新校验目录或重新检查环境。

## 5. 在终端安装和校验

在上面确定的命令执行端，用对应账户运行以下命令。模型包会校验并准备 OCR 模型。`knowledge setup` 会安装所需的 Python 依赖并复查。

```sh
npm install -g @himate/knowledge-models --registry http://10.143.57.12:4873 --allow-scripts=@himate/knowledge-models
npm install -g @himate/knowledge-cli --registry http://10.143.57.12:4873 --allow-scripts=@himate/knowledge-cli
knowledge --version
knowledge setup
knowledge doctor --environment-only
```

## 6. 文件上传与入库

点击「文件上传」，选择一批文件，再选择保存分类。

| 分类方式 | 操作 |
|---|---|
| 手动选择分类 | 选择目录后点「上传并保存」，整批文件直接保存到该分类 |
| 默认 AI 建议 | 点「上传并获取建议」，在同一窗口逐份查看和修改分类，再确认保存 |

上传过程中可以查看百分比进度。切到后台后，可以从完成提示或「上传记录」回到该批文件。AI 暂时无法给出建议时，也可以自己选择分类并确认保存。

保存成功后，在左侧「原始资料」查看文件。支持 Markdown、TXT、PDF、DOCX、XLSX、PPTX、HTML、CSV 和常见图片。上传 Markdown 时一并提供引用的本地图片。旧版 `.doc` 先转换为 `.docx`。

整批保存后，点完成弹窗的「开始入库」。OpenFlow 会为这一批新建会话并启动「知识入库」工作流。点「查看入库会话」查看进度，也可以从「上传记录」打开同一会话。工作流按本批清单逐份处理，完成每份原件的读取、审阅和发布后再处理下一份。长文档可能需要多轮，以会话最后的汇总为准。入库完成后，点会话输入框上方的「查看知识卡」进入知识页。

如果同一个知识库已有入库任务，页面会提供「查看当前入库会话」。当前任务结束后，可回到上传记录启动这一批。处理其他范围时，可手动运行「知识入库」工作流。项目已配置定时入库时，可按团队约定使用定时任务。

## 7. 查看和查询知识

入库完成后，点击知识库页头「刷新」，再查看以下三个页面。

| 页面 | 可以做什么 |
|---|---|
| 概览 | 查看知识卡数量、引用数量和最近更新 |
| 知识 | 按关键词和类型查找卡片，阅读正文，点击引用查看原文或代码 |
| 图谱 | 查看知识卡、文档和代码的关联，点击知识卡查看局部关系 |

普通引用按来源登记打开当前原件。行段引用显示原文行号并高亮引用位置，PDF 定位到引用页。原件变化后，通过重新入库或治理更新卡片。刷新期间有状态提示，失败时可以按提示修正后重试。由其他机器发布的卡片，先按项目流程同步到当前绑定的知识仓，再点「刷新」。

也可以直接让 Agent 查询，例如输入以下请求。

> 使用 hs-knowledge-query，帮我查一下 LLC 封装的帧格式。

Agent 会检索并阅读知识卡，回答时给出来源和适用条件。

## 8. 日常更新

- 更新或删除原始资料后，再运行「知识入库」。
- 需要批量核对来源和已引用代码的变化时，运行「知识治理巡检」。
- 需要把聊天结论整理为资料时，让 Agent 使用 `hs-knowledge-capture`，确认生成的原件后再入库。
- 更新工具时，重新执行 npm 安装命令、`knowledge --version` 和 `knowledge setup`。能力包更新后再运行 deploy 脚本，随后重启 OpenFlow。
- 安装或运行异常时，先在终端执行 `knowledge doctor --environment-only`，也可以从页面打开「环境检查」。更多安装参数和排查方式见工具包的[部署说明](../../himate-tools/docs/DEPLOY.md)。
