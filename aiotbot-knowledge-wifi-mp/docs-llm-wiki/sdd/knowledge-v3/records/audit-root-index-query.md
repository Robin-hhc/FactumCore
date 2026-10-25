# 索引、查询和有效性筛查

修改前公开回归已保存于 baseline-tests.json；5 项失败均报索引正文的 Windows 长路径缺文件。support 已有 native_path 写入，但 fixed_bytes 读取没有一致扩展，须修复读写而非缩短测试名。

| 差异 | 初始实现观察 | 修复与独立验收 |
|---|---|---|
| 索引共用能力 | SQLite 建表/写行私有于 index-build；verify 只校验数据库摘要和正文摘要，没有完整重算逻辑行 | contracts.indexing 共用构建/完整验证；完整比较卡/Claim/关系/分词/元数据/版本集合和值，不能仅查行数；缺/多/错值/额外表等独立预期用例 |
| 查询消费协议 | 已有资格先于 topK、部分 Claim 时抑制整卡元数据、generation/receipt 同代绑定和live重新检查 | 保留强保护；生产分词/正文读取调用同一 indexing；不得实现本轮暂缓的新 search 时效检查 |
| 跨机资格 | local/shared 构建均先要求本机 apply-result；query 又从私有 journal/.build 重演真人/代码证明，无法只拉正式仓消费 | 新 shared 接纳路径必须有安装器信任的签名、实际 Git 对象、卡与共享验收摘要同提交、规则/Claim/内容指纹一致；删除机器私有执行文件后仍可消费；本地脏摘要不可取得此资格 |
| 当前有效性 M | maintain 仅显式注册变化事件；P1 raw 未变时没有独立的代码/config/规则/已有待办比较入口 | 新 inspect-context 只读重建来源和配置限制及明确依赖，输出 affected_claims，交 P2—P5 修订，不凭扫描无变化清除限制 |

已有 public apply 资格、来源恢复、真实 Git publication、active CAS、writer barrier 和 receipt 检查保留；新摘要的 digest 只证明完整性，受信签名及实际 Git 内容才界定共享接纳边界。测试中的密钥和 Git 仓均为隔离合成机制，不代表真实 CI、真人或业务 Target。
