# 首批实施：T01 契约 CLI 与 T02 项目发现

本范围细化已批准详设 §3.1–3.3、§3.8、I0/I1，其他链路保持待开发。先通过行为测试，再写实现。接口不读取正式业务材料。

## T01 可运行契约入口

公开命令 `python skills/common/knowledge/_shared/cli.py contract validate --knowledge-root K --kind workspace|card|sources|record --input FILE`。输入支持受限安全 YAML/JSON；重复键拒绝。校验时只读取本地被框架锁固定摘要的 Schema/Profile/Registry，不运行提交中的 Python，不访问远端 $ref，不改输入。Schema/版本/锁/语义枚举错误给结构诊断及非零退出。

CLI 统一输出 `schema_version,status,operation_id,input_digests,output_refs,diagnostics,retryability,result`，成功退出0，参数/契约失败退出2，工具异常退出3；不输出 Python traceback 作为机器协议。`--version` 返回工具版本。规范化摘要采用 UTF-8、键排序、紧凑 JSON、禁止 NaN；外部输入路径与身份不会自动成为共享凭据。

实现 schema_version=1.0、七个 Profile、SourceResource/Snapshot/记录最小字段，明确 unknown；Schema 只能验证形状，不能替代断言语义检查。六 Target ID 为 chip12-host/device、chip08-host/device、chip07c-host/device；配置层校验同芯片 Host/Device pair、受控 source 引用和重复 ID，未配置路径返回 unknown，不宣称业务可用。条件组内 AND、组间 OR，不把 unknown 当 universal。

共享接口：`contracts.load_document(path)` 安全加载；`load_document_bytes(data,path)` 对调用者已经固定摘要的同一份字节解析，避免摘要/解析分别读取造成 A→B→A 错绑；`contracts.load_bundle(knowledge_root)` 校验本地规则锁；`contracts.validate_document(kind, document, knowledge_root)` 返回排序诊断列表；`scope.validate_configuration(config)` 检查六槽与三 pair/引用；`receipts.digest_json(value)`、`digest_file(path)`、`envelope(...)` 提供公共记录。诊断至少含 code、message、path。pinned/revalidate 缺少后续来源/门禁快照证明时保持 unknown，本切片不能判定版本资格。

## T02 发现与实际读取

公开命令 `project resolve --path PATH --registry REGISTRY [--base BASE] [--load-context] [--authorization-epoch EPOCH]`。registry 只定位显式登记的 workspace config，不能递归全盘扫描。相对代码路径没有 base 为错误；解析真实路径/联接点，按目录边界匹配，不按字符串前缀选仓。

`workspace.resolve_project(path, registry_path, base_path=None, load_context=False, authorization_epoch='local')` 返回 ProjectContextReceipt；CLI 包装同一接口。root 与代码模块映射来自当前配置，登记摘要失配则返回 REGISTRY_STALE。多个等优先匹配为 AMBIGUOUS_BINDING；只有显式覆盖允许嵌套选择。代码根未配置、路径不存在、登记或入口不可读明确诊断。registry/config 的解析与摘要绑定同一份字节。

Git 根、commit、origin 从真实元数据取得，不伪造 HEAD；全部 Git 调用禁用 fsmonitor。探测存在属性外部 helper 或子模块时，跳过可能执行命令/递归的 status，dirty=null 并给出原因与 unknown_fields，仍可完成元数据绑定及安全入口读取；其他 status 调用也忽略子模块。此处不证明 dirty 内容已取证，精确字节快照归 T04。外部配置、文件系统及进程权限仍由运行环境提供，不能声称已实施 ACL 或冻结恶意并发进程。

resolved 仅列所需入口；`--load-context` 才实际读取清单中每个入口，记录 path/digest/bytes/trace，全部成功才能 context_loaded。入口真实路径在读取前和末次复核都须留在其所属登记 workspace/知识根内，链接绕出拒绝。两阶段回执不宣称模型已经采纳，更不表示已检索知识或完成代码核验。用户级 Skill 安装及自然任务隐式触发率由后续独立任务验收，本轮不改用户全局设置。

首批验收包括合法/错误契约、篡改/远端 Schema、六槽三 pair 错配、unknown 精确匹配；任意 cwd、含空格中文路径、相对基准、边界前缀、歧义、失效登记、缺入口及真实工具读取。其他 E01–E08 未覆盖义务保持 planned/external_validation_required，不能把部分通过写作整个 I0/I1 完成。
