# 节点的 SSH 远端执行与本机部署

本工具运行 catalog 中已登记的公开节点。服务器工作区的所有项目命令统一通过 SSH 在服务器执行；Windows／Linux Agent 均可发起。Python、能力、代码、原件、卡、索引及子 CLI 使用服务器原生路径，不经 Samba／UNC／映射盘运行。真正位于当前机器本地磁盘的独立部署仍可本机执行。工具不替代 Agent 的内容阅读、独立复核或 ingest 编排，也不执行 Git 操作。

下文 `repo/` 仅表示项目根，`K` 表示 `config.yml` 中 WiFi 根解析出的实际知识根；允许 `K` 有多层前置目录。命令中的路径按实际部署位置取得，不要求目录真的叫 `repo`。Python、能力目录、catalog 和执行配置均属于各机器的部署配置。

## 1. 选择执行方式

每个 ingest 操作固定一种执行配置，整条链使用同一知识根、规则版本和能力 catalog。服务器工作区使用 `EXECUTION_MODE=ssh`（或 JSON `mode: ssh`），整个公共节点及其所有子 CLI 都留在服务器，不逐文件跨 SSH 调用 helper。准备环境、登记能力、扫描、规划、写稿、检查、索引、查询、源码定位及故障排查均在该端执行；读取证据和源码也通过 SSH 取得明确输出或必要文件，不在调用端遍历共享目录，不把知识库镜像到本地绕过此规则。

`mode: local` 仅用于代码、知识根、能力和 Python 确实位于当前机器原生本地文件系统的部署，包括直接在服务器本机运行的 Linux Agent；不要求它再建立 loopback SSH。跨主机的 Linux Agent 同样使用 SSH。`config.yml` 不变，SSH 路径填写服务器实际 POSIX 路径，不填写调用端的盘符。

Agent 的 Skill／Workflow 对所有上述项目操作执行这一规则。runner 另拒绝可识别的 UNC 和 Windows 网络映射盘入口，返回 `REMOTE_FILESYSTEM_REQUIRES_SSH`；它不会把网络路径转换成另一个执行方式。Linux 原生外观的目录可能是 CIFS 挂载点，本工具不据路径自动证明其文件系统类型；部署者须提供服务器原生本地目录。直接公开 CLI 和第三方工具继续由 Skill／Workflow 约束执行位置。

同一知识库同时最多一个 ingest。多个 query 可以并发，但每次使用独立 `operation_id`、调用者输出路径和 Workflow `run_id/node_id/attempt_id`。search 后的 read 沿原回执读取同代，仍会核验当前资格；来源或卡已变化时允许明确拒绝。

不会因为 SSH 失败、断线或执行结果缺失自动换成本机、Samba 或本地镜像执行，也不会自动重试有副作用的节点。先通过 SSH 检查原执行端的进程、操作记录、事务 journal 和活动索引，再决定续办。未配置 SSH 时先补齐配置，不先在共享盘试跑。

## 2. 本机配置

调用端先从受信分发包把配套 `tools/deploy/` 文件复制到本机磁盘的工具目录，以下称 `DEPLOY_LOCAL`；至少保持 `run_node.py` 与同目录 `install_catalog.py` 配套。调用端使用本机 Python 和 OpenSSH。不要从共享盘启动 Python 或 runner，也不需要把整个知识根复制到本地。服务器的 K 仍保留配套部署工具供远端 worker 使用。

将 [config.env.example](config.env.example) 放到本机私有配置目录并保存为 `config.env`，由用户填写。调用端的 runner、配套工具、Python、执行配置、catalog 副本、可选密钥、请求及响应副本都使用本机磁盘路径。本工具只在显式传入 `--config-env PATH` 时读取该文件，不搜索其他目录或隐式加载进程环境。真实 `config.env` 由 Git 忽略；不要把私钥、密码、令牌或主机实际值填回 example。

`config.env` 是严格的 UTF-8 数据：一行一个已知 `KEY=VALUE`，允许空行、整行 `#` 注释和整个值的单/双引号；不支持 `export`、转义、行尾注释、变量展开、命令替换或重复/未知键。不会 shell source/eval，也不会打印配置值。命令行中配置文件的位置相对调用时的当前目录；文件内部的调用端本机路径可用绝对路径、`~`，或相对该配置文件目录的路径。远端路径必须是 Linux 绝对 POSIX 路径。

服务器工作区填写模板中的 SSH 字段，见下一节。本机独立部署才使用 `EXECUTION_MODE=local`、`PROJECT_ROOT` 和 `CATALOG`；知识根从该项目的 `config.yml` 解析，规则摘要取匹配项目的登记项。`KNOWLEDGE_ROOT` 和 `RULES_DIGEST` 只作可选一致性限制，不需要重复手填。无法唯一定位登记项目或解释器时明确拒绝，不猜目录。

先在实际执行机器准备 Python 和能力目录，并用 `install_catalog.py --register-existing` 登记最终位置。把以下模板保存到部署者自己的配置目录，不放入原件、知识卡或共享项目映射；以安装结果和当前实际路径替换尖括号内容。

```json
{
  "schema_version": "1.0",
  "mode": "local",
  "knowledge_root": "<本机 K 的绝对路径>",
  "catalog": "<本机 catalog.json 的绝对路径>",
  "rules_digest": "<K/governance/framework.lock.yaml 原字节的 SHA-256>"
}
```

原有 JSON `--profile` 接口保持兼容；与 `--config-env` 二选一。执行配置只接受文中列出的字段；不接受来源提供的命令、自动执行方式或超时覆盖。catalog 中的 Python 是实际节点解释器，`run_node.py` 启动时所用 Python 不会取代它。路径与规则、解释器或能力字节变化后，按正常部署流程重新登记并更新配置，不手改旧摘要伪装原能力。

## 3. 配置 SSH 并在服务器登记

先通过 SSH 在服务器原生路径完成运行环境准备和最终能力登记，远端知识根必须具有本工具及同目录的部署工具文件。调用端可以使用既有 OpenSSH 主机别名/认证配置，也可以由用户在私有 `config.env` 填写 `SSH_HOST`（IP 或主机名）、`SSH_USER`、`SSH_PORT` 和 `SSH_IDENTITY_FILE`（本机私钥文件路径，工具不读取或打印私钥字节）。端口、用户、密钥可省略以沿用可信 OpenSSH 配置；显式端口与密钥分别通过 argv 的 `-p` / `-i` 传递，不作为 shell 命令片段。首次主机身份与认证由部署者预先配置；工具使用 `BatchMode=yes` 和 `StrictHostKeyChecking=yes`，不会关闭主机核验或开启交互式密码提示。

两种 SSH 配置共用 `ServerAliveInterval=30`、`ServerAliveCountMax=3`：连续 30 秒未收到服务端数据时，通过加密通道请求应答；服务端持续无应答时，约 90 秒后 SSH 连接会断开。长节点运行期间只要 SSH 服务端正常应答，连接可继续保持。节点原有 timeout 预算保持原样；工具不修改服务端或宿主 SSH 配置。保活可用于降低空闲连接被中间网络清理的风险，实际断连原因仍需现场证据确认；断连后按下文的远端状态核对流程处理，不自动重试或切换执行端。参数含义见 [OpenSSH 连接保活说明](https://man.openbsd.org/ssh_config.5#ServerAliveCountMax)。

推荐的 env 方式还填写 `REMOTE_PROJECT_ROOT`、`REMOTE_CATALOG` 和 `EXPECTED_CATALOG`。后者是远端 catalog 原字节在 Windows 的私有副本。工具从登记项取得该项目的规则摘要和节点解释器，按远端项目 `config.yml` 定位知识根与 runner，并在 worker 端再次核对项目登记、实际知识根、规则、catalog 和确切能力身份；不需要另手填相同内容的远端 JSON profile。`REMOTE_PYTHON`、`RULES_DIGEST` 可省略；显式规则摘要必须匹配登记。`REMOTE_PYTHON` 是可信启动器，可以是部署者提供的降权 wrapper，需接受 Python 的 `-B/-c` 参数并转发给实际运行环境；它不替换 catalog 中的业务节点解释器。没有真实远端 catalog 时应先完成登记和取回，不以默认目录猜测。

服务器工作区统一 SSH 是当前部署规则，不以某个 case 的性能报告为前置。它让密集文件校验及子进程靠近数据执行，并未证明所有操作都有同一倍数收益，也不保证既有 timeout 不再触发。执行配置不自动路由或跨端重试。

登记完成后，通过 SSH／SCP 将远端 catalog 的确切原字节取回本机私有目录，填入 `EXPECTED_CATALOG`。稿件和必要附件通过同样的连接定点传送到远端预期的 `.build/` 位置，后续请求使用远端知识根相对引用。能力文件（包括 SKILL.md）、解释器或登记路径变化后，在服务器重新登记，再更新本机 catalog 副本；不要修改旧 catalog 摘要伪装为原包。

以下旧 JSON 方式仍支持：远端另保存 `mode: local` profile，将远端 `catalog.json` 的确切原字节取回，并固定该 profile 原文件摘要。

将远端 `catalog.json` 的**确切原字节**取回 Windows 的私有配置目录，作为 `expected_catalog`。它只供校验，Windows 不会执行其中的 Linux 路径。取得远端本机执行配置原文件的 SHA-256，并保存下面的 Windows 配置：

```json
{
  "schema_version": "1.0",
  "mode": "ssh",
  "target": "<已配置的 SSH 主机别名，或 user@host>",
  "remote_python": "<Linux 启动器 Python 的绝对 POSIX 路径>",
  "remote_runner": "<Linux K/tools/deploy/run_node.py 的绝对 POSIX 路径>",
  "remote_profile": "<Linux 本机执行配置的绝对 POSIX 路径>",
  "remote_profile_digest": "<远端执行配置原字节的 SHA-256>",
  "expected_catalog": "<Windows 私有 catalog 副本的绝对路径>",
  "rules_digest": "<与远端执行配置相同的固定规则摘要>"
}
```

JSON 中 SSH 目标使用主机别名或 `user@host`，可选 `port` 和 `identity_file` 与 env 的端口/密钥字段等价。跳板等其他设置沿用 OpenSSH 的可信主机配置，不从请求或原件拼接额外参数。远端要求 Linux 与 POSIX 兼容 shell。工具将 Python、runner、项目和配置路径逐项进行 POSIX 引用，业务请求通过 stdin 传 JSON，不放进 shell 命令。

远端 worker 核对配置原字节、catalog 原字节和规则身份，然后只调用逻辑 Skill ID 对应的固定 `scripts/cli.py`。它使用远端 catalog 的能力与解释器，跨节点调用也继续留在远端；不会再跳回 Windows。结果同时核对原协议摘要、规则、节点身份、包摘要和退出状态；旧 catalog 副本或配置摘要会被明确拒绝。

文件摘要可用实际运行 Python 的标准库计算，`PATH_TO_FILE` 替换为实际文件参数：

```text
python -c "import hashlib,pathlib,sys; print(hashlib.sha256(pathlib.Path(sys.argv[1]).read_bytes()).hexdigest())" PATH_TO_FILE
```

## 4. 调用与产物路径

在调用端使用本机 Python 启动 `DEPLOY_LOCAL/run_node.py`，传入本机私有配置、逻辑节点、本机请求以及新的本机输出路径。`PATH_TO_RUN_NODE` 指该本机工具副本，不能指向服务器知识根的映射盘：

```text
python PATH_TO_RUN_NODE --profile ABS_PROFILE --skill hs-knowledge-source-scan --action status --input ABS_REQUEST --output NEW_ABS_OUTPUT
```

用户填写的 env 方式：

```text
python PATH_TO_RUN_NODE --config-env PATH_TO_PRIVATE_CONFIG_ENV --skill hs-knowledge-source-scan --action status --input ABS_REQUEST --output NEW_ABS_OUTPUT
```

例如请求为 `{"operation_id":"status-unique-id","target_operation_id":"ingest-operation-id"}`。每个独立操作使用安全且独立的 `operation_id`；同一 ingest 的跨节点调用沿用原操作 ID，调用尝试由 Workflow 身份或执行目录的 UUID 隔离。`--action` 可省略，由节点自己的公开协议决定默认动作；该入口运行单个节点，不把整条 Workflow 当作节点运行。

执行端持久保存：

```text
K/.build/operations/<operation_id>/execution/<unique-call-id>/request.json
K/.build/operations/<operation_id>/execution/<unique-call-id>/response.json
```

这些位置属于执行端的知识根，SSH 断线后也可以按 operation_id 检查。调用者 `--output` 是原响应的本机副本，必须是新文件，不会覆盖既有输出。本机与 SSH 模式都禁止把副本或错误报告写入调用端已有知识根的原件、正式卡、治理目录和 `logs/ingest/` 等正式记录；位于知识根内时只允许 `.build/` 或专用 `logs/execution/`。受控的事务/事件/Workflow 路径也不作任意副本输出区。该保护检查所有多层嵌套知识根，仅查看路径和规则锁标记，不加载候选程序。配置、catalog 或能力在运行中变化时，返回独立的 `execution_error`，不能将它当节点成功结果。

普通节点沿用 `ResultEnvelope` 的退出 0/2/3。lint 沿用自己的 `CheckReport 1.0` 与退出 0/1/2，不包装成普通节点成功结果。完整 lint 报告由真实 CLI 校验并写入执行端持久目录，runner 保留其原字节；没有有效报告文件的启动故障只返回执行错误，不伪造通过报告。

`data.report_ref`、`view_ref`、`apply_result_ref`、receipt 和其他产物引用继续按**执行端知识根**解释。本机响应副本不是远端 P6/P7 所需的报告或 apply 证明文件。lint 自身返回的 `data.report_ref` 为执行端绝对路径；后续要求知识根相对引用的接口，应按该执行端的 K 计算相对路径，例如 `.build/operations/.../execution/.../response.json`，不修改或重签报告正文。SSH 的 POSIX 路径不可用 Windows 盘符转换规则猜测。

## 5. 验证与故障处理

验收服务器部署时，从调用端经 SSH 运行 status、目标 query 和独立的测试材料批，检查实际 phase、报告、远端产物及同代读取；另验证服务器本机 CLI、连接中断后状态核对和网络路径拒绝。普通本机部署的测试与跨主机 SSH 结果分别记录，隔离传输测试不代替真实主机认证、权限或内部 Agent 接入。

`benchmark_execution.py` 与已有 SMB 配对报告保留为历史实验和性能分析材料；常规执行入口的网络路径拒绝同样作用于其真实 dispatch，不提供 SMB 绕过开关。历史 report 的 `ssh_candidate_for_this_bound_case` 描述当次具体 case 的结果，不再决定当前部署是否要求 SSH。后续测量需固定输入、配置、规则、包、依赖、活动代次及结果语义；空命中、失败或截断不算完成同样工作，跨 WAN／隧道结果不推算成内部 ingest 的速度。

历史共享盘试验曾在 NTFS junction 创建和 Windows Git 跨所有者仓库前提处失败，相关原始结果保留。当前通过服务器实际用户及原生路径执行历史回源，不自动放宽 Git 全局信任；固定证据对象和真实 Git 历史仍分别验证。

`SSH_RESULT_UNAVAILABLE_REMOTE_STATE_UNKNOWN` 表示没有收到可验证结果，不证明远端没有执行或已经停止。保留 operation_id，不创建新 ingest 盲目重放；先在远端查看 `.build/operations/<operation_id>/execution/`、实际节点记录、`logs/operations/<operation_id>/journal.json` 与活动索引。远端状态、规则或输入不再一致时按原工作流的恢复/修订规则处理。工具不改变已有节点 timeout 策略。

引用依据：[OpenSSH ssh 手册](https://man.openbsd.org/ssh.1)、[Python POSIX shell 引用说明](https://docs.python.org/3/library/shlex.html#shlex.quote)。
