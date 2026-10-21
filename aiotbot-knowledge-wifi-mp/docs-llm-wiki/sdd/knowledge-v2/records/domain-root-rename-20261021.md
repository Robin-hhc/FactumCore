# WiFi领域根添加-mp后缀

日期：2026-10-21。用户明确要求全局改名并上库。迁移前提交：`368a37ae6fa28a7d5ed0007eb7d8ec0c11a2214e`。

## 范围与历史身份

- 当前唯一领域根由`aiotbot-knowledge-wifi/`改为`aiotbot-knowledge-wifi-mp/`；迁移原领域根下194个已跟踪文件，域内相对路径保持不变。
- 同步现行AGENTS、主设计/详设/使用说明、config、Git属性与忽略规则、SDD现行追踪路径、安装器及测试/验收夹具。WiFi领域ID、六Target/三pair、18节点和两个Workflow不变，不增加功能任务或Demo范围。
- `knowledge-v1/`的95个文件、v2的`baseline.json`及既有6份实施/验收/发布记录，共102个文件按迁移前后同一领域内相对路径逐文件比对，SHA-256全部一致。历史内容中的旧根指向原提交位置；查当前文件时只对物理路径前缀应用上述映射，不改写原记录、旧摘要、签名或成绩。
- 现行目录及入口使用新根；不存在旧根别名或嵌套Git。原件与已有本地产物随目录整体迁移，内容不批量替换。既有本机安装和宿主登记不在本次公共仓改名中自动更新。

## 实际验证

| 检查 | 本次结果 |
|---|---|
| 改名前安装/项目绑定与纯契约回归 | 51 passed，1 skipped（Windows符号链接创建条件） |
| 新根下18节点/两个Workflow静态检查 | static_valid，0 errors |
| 新根下全部Skill与evals的ruff检查 | All checks passed |
| 新独立目录安装及workspace登记 | 18包、2模板；登记读取新领域根的规则锁；未注册到真实宿主 |
| 历史原字节与规则锁核对 | 102个历史文件一致；framework.lock原字节不变 |
| 改名后全量合成机制回归 | 200项，197 passed、3 skipped，0 failures、0 errors |

规则锁摘要仍为`06b24f9c5059cac9600978297a1dacf9c4c0353a0fde73302f16d493a2f8529b`。安装器现行路径修改使`hs-workspace-explore`包摘要变为`55e390e30597e44665fb930d5b7da0b444a8e76d87af98cc65b67f776beee39f`；新独立安装按当前源码生成catalog，旧包身份不改写。

此次只验证目录、引用与隔离合成机制。T211真人、隐式宿主、真实六Target、业务CI及ACL条件保持原状态，不因改名关闭。既有`implementation-manifest.json`仍描述原runtime_commit，本次改名的源码身份和结果单独记录。

首两轮因Windows长路径限制分别出现7项和5项失败（对象路径263字符、索引卡路径272字符）。只缩短测试harness及runner的临时目录层级，保持测试集合、断言与生产逻辑不变后，使用短输出目录r2完成上述全量回归。3项跳过分别为Windows符号链接创建、固定OpenFlow loader集成和显式POSIX shell包装器检查；本次未提供后两项的外部环境，未将这些检查计为通过。这不表示生产程序已新增Windows长路径支持。详细结果和当前改动文件身份见[机器记录](domain-root-rename-20261021.json)。

机器记录中的改动文件摘要使用暂存Git blob的规范化字节；测试在实际工作树执行，规则与节点包摘要另按实际文件字节验证。
