---
id: hi1105-host-rx-netif-delivery
doc_ref:
- doc_id: doc-80fcddc5f82362442e52
  line_start: 11
  line_end: 30
code_ref:
- code_id: code-77e44563f471c8a40824
  symbol: hmac_rx_skb_netif_rpt
  line_start: 864
  line_end: 883
- code_id: code-09c5d0d222a59e6a0e23
  symbol: hmac_rxdata_netbuf_enqueue
  line_start: 1185
  line_end: 1197
- code_id: code-77e44563f471c8a40824
  line_start: 1447
  line_end: 1455
- code_id: code-09c5d0d222a59e6a0e23
  line_start: 1145
  line_end: 1152
- code_id: code-09c5d0d222a59e6a0e23
  line_start: 1199
  line_end: 1269
- code_id: code-77e44563f471c8a40824
  symbol: hmac_rxdata_netbuf_delist
  line_start: 841
  line_end: 862
- code_id: code-d0a551808e381b01520e
  symbol: wal_init_netdev_priv
  line_start: 6966
  line_end: 6977
- code_id: code-09c5d0d222a59e6a0e23
  symbol: hmac_rxdata_polling
  line_start: 1292
  line_end: 1343
tags: [wifi, hi1105, host, linux, rx, napi, gro]
lifecycle: stable
---
# HI1105 Host 接收上报的直接交付、接收线程与 NAPI

在测试提交 `2ff14bf7441b` 的 HI1105 Host 源码中，已准备交给网络设备的接收帧，从 `hmac_rx_skb_netif_rpt` 进入上报流程。接收线程开关决定入口直交或入队，接口的 NAPI 和 GRO 状态分别影响出队与上报。

## 入口如何选择直交或入队

入口以 `oal_eth_type_trans` 设置 skb 的协议类型。接收线程关闭时清理控制缓冲区，调用 `oal_notice_netif_rx` 和 `oal_netif_rx_ni`。线程开启时调用 `hmac_rxdata_netbuf_enqueue` 并返回。入队函数取网络设备私有接收队列，**已有长度严格大于 `queue_len_max`** 时释放当前帧，其余情况从队尾加入。代码依据：`code-77e44563f471c8a40824` 的 `hmac_rx_skb_netif_rpt`，`code-09c5d0d222a59e6a0e23` 的 `hmac_rxdata_netbuf_enqueue`。

## 接收线程如何选择出队方式

以 `hmac_rx_lan_frame` 为例，Linux 路径在批末且接收线程已使能时，通过 `hmac_rxdata_sched` 唤醒线程。线程处理具有网络设备、私有结构和非空队列的 VAP。它读取接口 NAPI 使能状态。若使能，先调用 `hmac_rxdata_update_napi_weight`，再读取当时的权重。编译启用 `_PRE_CONFIG_NAPI_DYNAMIC_SWITCH` 且该权重不大于 1 时，本轮转为线程直接出队。其余情况下按最终调度状态调用 `oal_napi_schedule` 或 `hmac_rxdata_netbuf_delist`。线程直交路径逐帧清理控制缓冲区并调用 `oal_notice_netif_rx` 和 `oal_netif_rx_ni`。代码依据：`code-77e44563f471c8a40824` 的 1447–1455 行及 `hmac_rxdata_netbuf_delist`，`code-09c5d0d222a59e6a0e23` 的 1145–1152、1199–1269 行。

## NAPI 回调如何上报

`wal_init_netdev_priv` 初始化接口接收队列，并注册 `hmac_rxdata_polling`。回调按本轮预算从该队列出队，清理每帧的控制缓冲区。GRO 使能时调用 `oal_napi_gro_receive`，否则调用 `oal_netif_receive_skb`。队列取空时停止。本轮处理数小于传入权重时调用 `oal_napi_complete`。若预算被缩短且循环没有观察到队列取空，则调用 `hmac_rxdata_sched` 请求接收线程再次处理。代码依据：`code-d0a551808e381b01520e` 的 `wal_init_netdev_priv`，`code-09c5d0d222a59e6a0e23` 的 `hmac_rxdata_polling`。

## 适用范围

本卡止于 OAL 上报接口。源码展示开关、宏和预算条件，实际固件的宏配置、接口开关值及运行效果需单独核实。