# FactumCore 知识库系统：待解决问题清单（2026-10-28）

## 出现了query执行慢问题：
  主要阻塞：hs-knowledge-query 搜索一直返回空结果

  这是 90% 的时间都花在这的地方。我连续试了 3 个查询词都返回空 matches，而知识库明明有 4 张 HWDL 卡。原因有两层，都不直观：

  purpose 不匹配：这些卡（hwdl-tx-flow 等）是设计文档卡，claim 的 usage 是 guidance。而 match_scope 里 purpose=current 时 claim.usage != "current" 直接判   False。所以我最初用默认的 purpose: current 查，永远命中不了。SKILL 文档里没写明这条，我是去读了 query_runtime.py 源码才发现的。
  context 必须带全 chip/side/features：卡的 scope 是 constrained（chip08-host/chip07c-host + _PRE_WLAN_FEATURE_HWDL），match_scope 要求 context 的 chip、side、features   全部对上才匹配。我最初只传了 {"side": "host"}，缺 chip 和 features，又被过滤掉。

  最终用 purpose: guidance + context: {chip: chip07c, side: host, features: [_PRE_WLAN_FEATURE_HWDL]} 才命中。这个过程我读了   public-api.md、support.py、node.py、query_runtime.py 四份代码才定位到原因，轮次很多。

  次要耗时（非阻塞，但浪费时间）

  - 后台 grep 超时：在 main/ 大目录下全仓 grep 超过 120s 默认超时被后台化，等它跑完。后来改用带 --include 的定向 grep 快很多。
  - CodeGraph 不可用：想用 codegraph 查引用，但本地没加载 thursday 项目（代码在远程服务器），直接报错，只能退回 grep。
  - 几次工具参数序列化错误（bash 调用格式问题）重试了 3-4 次。

  改进方向

  这次知识库查询的"正确姿势"（purpose 必须用 guidance、context 要带 chip+features）SKILL   文档没写清楚。建议可以考虑把这条经验记入知识库使用说明，下次直接一步命中。
