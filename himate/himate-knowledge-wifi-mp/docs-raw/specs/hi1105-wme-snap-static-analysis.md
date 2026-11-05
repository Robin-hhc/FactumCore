# 本次复制源码的静态分析记录：WME 映射与 SNAP 封装

记录日期：2026-10-30。
资料性质：本次真实源码静态阅读记录，用于知识入库试运行；不是经批准的产品设计或标准符合性报告。
代码基准：从实际源目录复制到项目 `main/` 的文件，复制字节一致性由本次运行另行核验。
范围：`main/hi1105_host/` 与 `main/hi1102_device/` 中下列宏和函数。
所有结论仅描述列明文件的静态实现，不推断启用的芯片、宏组合、构建版本或跨二进制调用关系。

## 1. WME TID 与 AC 映射

实现入口：
- Host：`main/hi1105_host/inc/hd_common/wlan_types.h`，`WLAN_WME_AC_TO_TID` 第186—187行，`WLAN_WME_TID_TO_AC` 第206—208行。
- Device：`main/hi1102_device/inc/wlan_types.h`，`WLAN_WME_AC_TO_TID` 第155—159行，`WLAN_WME_TID_TO_AC` 第163—167行。

两份 `WLAN_WME_TID_TO_AC` 宏的分支相同。
对输入0～7，映射结果如下：
- 0、3 → `WLAN_WME_AC_BE`。
- 1、2 → `WLAN_WME_AC_BK`。
- 4、5 → `WLAN_WME_AC_VI`。
- 6、7 → `WLAN_WME_AC_VO`。

最后一支为无条件默认分支；宏本身没有把输入范围限制为0～7。
不能根据上述表格声称越界输入会被拒绝。

两份 `WLAN_WME_AC_TO_TID` 也采用相同代表值：VO→6、VI→5、BK→1、其他→0。
因此 AC→TID 不是 TID→AC 的逆操作，不能恢复原来是0还是3等信息。
定位优先级错误时，应区分“归入哪个AC”与“从AC选哪个代表TID”两个问题。
本记录没有验证该宏的所有调用点或调用前校验。

## 2. SNAP 组织码分支与 EtherType 参数

实现入口：
- Host：`main/hi1105_host/hmac/mac_frame_inl.h`，`mac_set_snap` 第178—206行。
- Device：`main/hi1102_device/inc/dmac/mac_frame.h`，`mac_set_snap` 第2468—2502行。

两份实现都先将 `ETHER_TYPE_AARP`、`ETHER_TYPE_IPX` 用 `oal_byteorder_host_to_net_uint16` 转换。
传入的 `us_ether_type` 与这两个转换后的值比较。
命中任一个时，组织码三个字节使用 `SNAP_BTEP_ORGCODE_0/1/2`。
其他分支使用 `SNAP_RFC1042_ORGCODE_0/1/2`。
本次只确认宏选择逻辑，不用注释替代外部宏定义来证明最终数值。

两份实现都设置 LLC DSAP/SSAP 为 `SNAP_LLC_LSAP`，控制字段为 `LLC_UI`。
随后都将传入的 `us_ether_type` 原值赋给 SNAP 的 `us_ether_type` 字段。
该赋值处没有再执行一次字节序转换。
排查 AARP/IPX 分支未命中时，应先核对传入参数与比较常量的字节序是否一致。
“BTEP”“RFC1042”在这里描述源码分支命名，不表示本次已完成协议标准逐条验证。

## 3. 同名 SNAP 函数的偏移接口不同

Host 签名接收 `pst_buf` 和 `us_ether_type`，没有单独的offset参数。
Host 用 `ETHER_HDR_LEN - SNAP_LLC_FRAME_LEN` 计算 SNAP 写入位置。
Host 完成字段写入后，以同一表达式执行 `oal_netbuf_pull`。

Device 签名除 `pst_buf`、`us_ether_type` 外，还接收 `uc_offset`。
Device 使用 `oal_netbuf_data(pst_buf) + uc_offset` 计算 SNAP 写入位置。
Device 完成字段写入后，以 `uc_offset` 执行 `oal_netbuf_pull`。

所以两份同名函数的调用参数不能机械互换；在比较封装位置时应核对各自接口。
本记录没有证明调用者如何准备缓冲区、实际offset取值或头部空间。
也没有证明任一完整发送流程一定调用到这两个函数。

## 4. 文件编码与来源保留

以上四份文件均不能严格按UTF-8解码，但可以严格按GB18030解码。
阅读工具展示的部分注释可能因错误解码而乱码；本记录依据实际代码分支、参数和赋值。
应保留来源原字节，在来源操作中明确编码，不把转码后的副本冒充原文件。
文件SHA-256：
- Host `inc/hd_common/wlan_types.h`：`670c7b4b25497b378597adf914ba539a19f01aded9ad4dea9c70404dd907f3dd`。
- Device `inc/wlan_types.h`：`f05b418dc2fc0d6885b1a977d63a9545c84f732b680ddae6e069c36b79d1c13c`。
- Host `hmac/mac_frame_inl.h`：`0574e8d94181d86dce2b83d5b43a98d6cc81d35daca79f019a4cf26cb03cf254`。
- Device `inc/dmac/mac_frame.h`：`0a678883c5907d39988f89350d3c44232aec575fc10d2976c2c1c64a6b332114`。

## 5. 未验证范围

未编译、未运行驱动、未连接硬件、未验证报文抓包结果。
未核对外部协议原文、所有宏定义及调用者提供的缓冲区条件。
本次观察适合形成“静态实现与定位指引”，不能升级为产品运行保证或标准符合性结论。
