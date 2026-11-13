# HI1105 Host 接收上报：直接交付、接收线程与 NAPI

## 问题与范围

HI1105 Host Linux 路径里，已经准备交给网络设备的接收帧如何进入协议栈？分析从 `hmac_rx_skb_netif_rpt` 开始，沿直接上报和接收线程两条路径追到实际调用的 OAL 接口。这里的直接交付指驱动调用 `oal_netif_rx_ni`，后文区分由入口直接调用和由接收线程出队后调用的情况。

依据为测试仓提交 `2ff14bf7441b1d9d4a73a1a7e886173cd0034a82`。下列位置均为项目根相对路径，三个引用文件在独立验收工作区的 SHA-256 与该测试仓一致。

## 结论与依据

### 接收帧交给网络设备

`hmac_rx_skb_netif_rpt` 先以 `oal_eth_type_trans(netbuf, net_dev)` 的返回值设置 `protocol`。接收线程已使能时，它调用 `hmac_rxdata_netbuf_enqueue` 后返回。接收线程未使能时，它清理 skb 控制缓冲区，调用 `oal_notice_netif_rx`，然后调用 `oal_netif_rx_ni`。
依据：`main/hi1105_host/hmac/hmac_rx_data.c:864-883`，`hmac_rx_skb_netif_rpt`。

`hmac_rxdata_netbuf_enqueue` 从 skb 对应网络设备的私有结构取得接收队列。若入队前已有的队列长度严格大于 `queue_len_max`，就释放本帧并返回。其余情况从队尾加入并更新计数。
依据：`main/hi1105_host/hmac/hmac_main.c:1185-1197`，`hmac_rxdata_netbuf_enqueue`。

### 接收线程决定何时走 NAPI

以 `hmac_rx_lan_frame` 处理一批帧的路径为例，循环结束时若接收线程已使能，调用 `hmac_rxdata_sched`。在 Linux 条件下它唤醒等待信号量的接收线程，线程调用 `hmac_exec_rxdata_schedule_process`。后者遍历 VAP，仅处理具备网络设备、私有结构和非空接收队列的接口。
依据：`main/hi1105_host/hmac/hmac_rx_data.c:1447-1455`，`hmac_rx_lan_frame`；`main/hi1105_host/hmac/hmac_main.c:1145-1152`、`1199-1224`、`1247-1269`，分别为唤醒、遍历和线程循环。

接收线程从接口私有结构的 `uc_napi_enable` 取得调度状态。若使能，它先调用 `hmac_rxdata_update_napi_weight`。编译启用 `_PRE_CONFIG_NAPI_DYNAMIC_SWITCH` 且当前 `uc_napi_weight <= 1` 时，本轮切到直接出队。最终调度状态为真时调用 `oal_napi_schedule`。否则，线程调用 `hmac_rxdata_netbuf_delist`，逐帧清理控制缓冲区，再依次调用 `oal_notice_netif_rx` 和 `oal_netif_rx_ni`。
依据：`main/hi1105_host/hmac/hmac_main.c:1226-1242`，`hmac_exec_rxdata_schedule_process`；`main/hi1105_host/hmac/hmac_rx_data.c:841-862`，`hmac_rxdata_netbuf_delist`。

### NAPI 回调交给协议栈

`wal_init_netdev_priv` 初始化接口接收队列，并使用 `oal_netif_napi_add` 注册 `hmac_rxdata_polling`。回调按本轮允许的帧数从同一队列出队，逐帧清理控制缓冲区。接口的 `uc_gro_enable` 为真时调用 `oal_napi_gro_receive`，否则调用 `oal_netif_receive_skb`。队列取空会结束本轮出队。处理数小于原始 `l_weight` 时调用 `oal_napi_complete`，若本轮预算被缩短且循环未观察到队列取空，则请求再次调度。
依据：`main/hi1105_host/wal/wal_linux_ioctl.c:6966-6977`，`wal_init_netdev_priv`；`main/hi1105_host/hmac/hmac_main.c:1292-1343`，`hmac_rxdata_polling`。

## 未核实范围

本次核查的是 HI1105 Host 对应快照的源码。宏和接口开关只按代码中的条件说明，具体固件的编译选项、运行时开关取值、实际上报频率和吞吐均未采集。范围从向网络设备上报的函数开始，止于调用 OAL 上报接口。
