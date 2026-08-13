# WiFiDemo 目标工作负载案例集

源码根目录：`E:/WiFiDemo/WiFiDemo`
核验日期：2026-08-13

## 1. 使用边界

本案例集只说明与工业 WiFi MAC 相似的代码结构为什么会影响知识架构。它不运行或评价任何候选工具，不产生准确率、召回率、Token、延迟或成本结论。源码行号来自上述目录的当前 checkout；正式 Benchmark 必须再固定 commit。

每个案例回答六件事：问题模式、最小代码证据、为何普通调用图不足、知识架构必须表达什么、代码与领域知识如何连接、本研究不声称什么。

## W01 — Host 共代码包含多芯片实现

**问题模式**

Host target 同时编译 chip2 和 chip8 的实现，芯片差异主要在运行时选择。源码目录名不能直接等价于“只存在于该芯片 Target”。

**代码证据**

- `host/CMakeLists.txt:17-24`：同一个 `chip` 静态库同时包含 `chip_chip2.c` 与 `chip_chip8.c`。
- `host/CMakeLists.txt:56-70`：同一个 `hal` 静态库同时包含 chip2 和 chip8 的 HAL product 源文件。

```cmake
set(CHIP_SOURCES
    ${CMAKE_SOURCE_DIR}/host/wifi/chip/chip_common.c
    ${CMAKE_SOURCE_DIR}/host/wifi/chip/chip_chip2.c
    ${CMAKE_SOURCE_DIR}/host/wifi/chip/chip_chip8.c
)
add_library(chip STATIC ${CHIP_SOURCES})
```

**为什么普通调用图不足**

调用图能够显示函数之间的边，但无法仅凭文件路径决定当前 `chip2-wifi-host` 或 `chip8-wifi-host` 应采用哪张 ops 表。把 `chip_chip8.c` 中的函数永久标成“仅 chip8”会丢失 Host 共代码的编译事实。

**架构要求**

区分 Source Function、Target occurrence 和运行时实现候选；查询必须携带 Target，并允许一个 Target 中同时存在多个芯片实现。

**代码—领域知识链接要求**

“chip8 实现”“Host 共代码”等标签必须链接到具体 revision、Target occurrence 和选择逻辑证据，而不是只链接文件夹名称。

**当前研究不声称**

不声称任何候选工具已经能自动恢复正确的运行时绑定。

## W02 — Device 按芯片选择源码与宏集

**问题模式**

Device 与 Host 的构建组织不同：Device 在配置阶段按 `CHIP_TYPE` 选择独立宏文件和源集合。

**代码证据**

- `device/CMakeLists.txt:5-9`：按 chip2/chip8 include 不同 `macro_config.cmake`。
- `device/CMakeLists.txt:21-50`：chip2 和 chip8 进入互斥的 `CHIP_SOURCES` 分支。
- `device/wifi/chip2/macro_config.cmake:12-17` 与 `device/wifi/chip8/macro_config.cmake:13-23`：两芯片宏集合不同。

```cmake
if(CHIP_TYPE STREQUAL "CHIP2")
    include(${CMAKE_SOURCE_DIR}/device/wifi/chip2/macro_config.cmake)
elseif(CHIP_TYPE STREQUAL "CHIP8")
    include(${CMAKE_SOURCE_DIR}/device/wifi/chip8/macro_config.cmake)
endif()
```

**为什么普通调用图不足**

在未绑定构建配置的源码并集上建图，会让互斥 Device 实现同时出现，制造当前 Target 不可能存在的调用候选。

**架构要求**

代码事实必须对应真实或等价的编译视角；Target 是开放标识，chip、side 和 product 是维度而不是硬编码枚举。

**代码—领域知识链接要求**

Feature 或芯片能力标签应链接到 Target Profile 和宏来源；不能把 `_PRE_WLAN_FEATURE_11AX` 的 chip8 事实扩散到 chip2 Device。

**当前研究不声称**

不把“支持 C/C++”视为已证明支持 Target-specific preprocessing。

## W03 — Target-specific 宏改变 Host 代码存在性

**问题模式**

Host 大部分源码共用，但 `_PRE_WLAN_FEATURE_HOST_TX_OFFLOAD` 只在 chip8 Host Target 中定义。

**代码证据**

- `build.py:14-35`：四个公开构建 Target 分别组合 chip2/chip8 与 host/device。
- `host/CMakeLists.txt:9-14`：仅 `CHIP_TYPE=CHIP8` 追加 offload 宏。

```cmake
if(CHIP_TYPE STREQUAL "CHIP8")
    list(APPEND wifi_common_macro -D_PRE_WLAN_FEATURE_HOST_TX_OFFLOAD)
endif()
add_definitions(${wifi_common_macro})
```

**为什么普通调用图不足**

源文件相同不代表函数体和调用边相同。没有 Target Profile 的统一图无法说明 `dpa_forward_to_device` 调用在 chip8 Host 中有效而在 chip2 Host 中被裁剪。

**架构要求**

区分 Target 全量宏环境与单个函数相关条件；Function occurrence、call edge 和源码证据必须能追溯到生成它们的编译配置。

**代码—领域知识链接要求**

领域概念 `TX_OFFLOAD` 应通过宏、Target 和有效源码 occurrence 连接到代码，不能只靠函数名推断。

**当前研究不声称**

不在本阶段执行四 Target 构建，也不使用该案例比较工具准确率。

## W04 — 条件编译同时改变 HCC 与 HMAC 路径

**问题模式**

同一个宏在多个模块改变控制路径，领域含义不是单一 `#ifdef` 节点能够表达的。

**代码证据**

- `host/wifi/dpe/hcc/hcc_core.c:202-214`：宏开时调用 `dpa_forward_to_device`，宏关时调用 `hcc_tx_queue_put`。
- `host/wifi/hmac/tx/hmac_tx_data.c:66-78`：宏开时 DEVICE_RING 可跳过 `hmac_tx_fill_seqno`，宏关时始终填充 seqno。

```c
#if defined(_PRE_WLAN_FEATURE_HOST_TX_OFFLOAD)
    return dpa_forward_to_device(msg);
#else
    return hcc_tx_queue_put(msg);
#endif
```

**为什么普通调用图不足**

无条件调用图可能同时保留互斥边，也可能只解析某一默认宏视角。仅知道“函数属于 TX”不能证明它位于哪条有效执行路径。

**架构要求**

支持 Target-local call/CFG 查询，并把源码条件作为解释证据。Flow 标签只能用于导航，不能冒充已证明路径。

**代码—领域知识链接要求**

`TX_OFFLOAD`、`DEVICE_RING` 和“轻量帧准备”之间的领域关系应连接到宏条件、状态判断和两个模块的源码证据，并标明哪些关系是人工解释。

**当前研究不声称**

不声称静态分析必然能够完全恢复宏与运行时 Ring 状态组合。

## W05 — ops 与规格表在运行时选择

**问题模式**

芯片差异通过函数指针表和全局规格表选择，而不是普通直接调用或单一编译期宏。

**代码证据**

- `host/platform/main/platform_main.c:31-53`：`platform_init` 依次执行 `chip_init`、`hal_ops_select` 和 `spec_select`。
- `host/wifi/chip/chip_common.c:13-25`：`chip_ops_select` 根据 `chip_type` 复制不同 ops 表。
- `host/wifi/dpe/hal/hal_main.c:83-94`：`g_hal_common_ops` 在运行时取 chip2/chip8 表。
- `host/wifi/common/wlan_spec.c:15-41`：`g_wlan_spec_cfg` 从不同芯片规格填充。

```c
if (chip_type == CHIP_TYPE_CHIP8) {
    g_wlan_chip_ops = g_wlan_chip_ops_chip8;
} else if (chip_type == CHIP_TYPE_CHIP2) {
    g_wlan_chip_ops = g_wlan_chip_ops_chip2;
}
```

**为什么普通调用图不足**

`ops->member()` 的最终实现依赖初始化顺序、赋值表和运行时 `chip_type`。将所有表项连成确定调用会产生假阳性；自动选择一个实现又可能产生假阴性。

**架构要求**

表示 indirect-call site、候选实现、赋值来源、选择条件和证据。无法唯一解析时返回候选集合并允许 abstention。

**代码—领域知识链接要求**

“chip8 支持某能力”的领域结论应从规格字段或 ops 实现回链到选择条件，且与 Target 编译事实分开。

**当前研究不声称**

不要求当前调研证明某个引擎能自动完成全部函数指针解析。

## W06 — Host/Device Event 跨越独立编译视角

**问题模式**

Host producer 与 Device consumer 不构成 C 语言直接调用；链路通过共享消息结构、HCC、回调和 FRW 注册表连接。

**代码证据**

- `shared/include/wifi_hcc.h:13-38`：Host/Device 共用通道、消息头和 `hcc_tx_msg_stru`。
- `host/wifi/dpe/hcc/hcc_core.c:202-214`：Host 发送 TX 事件。
- `device/wifi/chip8/hcc/hcc_device.c:79-107`：Device 按 channel/msg_type 调用注册的 `g_frw_dispatch`。
- `device/wifi/chip8/frw/frw_event.c:12-35`：FRW 根据事件头查找处理入口。
- `device/wifi/chip8/frw/frw_event_main.c:103-130`：注册 HCC dispatch 和事件表。

```c
if (g_frw_dispatch != NULL) {
    g_frw_dispatch(data);
}
```

**为什么普通调用图不足**

Host 和 Device 通常生成不同 CPG/索引；跨侧关系由协议字段而非链接器符号建立。把 producer 到 consumer 伪造成 `CALLS` 会隐藏通信边界和多候选 handler。

**架构要求**

Event/Message 是一级实体，保存 producer、consumer、side、Target、subtype、注册证据和候选集合；Agent 再选择另一个编译视角继续查询。

**代码—领域知识链接要求**

事件名称、协议含义和设计约束需要链接到共享结构定义、producer、注册表与 consumer，而不是只链接一端函数。

**当前研究不声称**

不声称 Event 在所有 Target 中具有唯一 producer 或 consumer。

## W07 — 公共源码归属与 Target occurrence 分离

**问题模式**

`hcc_core.c` 等 Host 公共源码参与多个 Host Target，但其中部分边受 chip8 专用宏控制。源码身份、编译存在性和芯片领域归属是三种不同关系。

**代码证据**

- `build.py:25-34`：chip2/chip8 Host 是两个 Target。
- `host/CMakeLists.txt:9-14`：两个 Host Target 只有 offload 宏差异。
- `host/wifi/dpe/hcc/hcc_core.c:202-214`：同一源码函数在两个 Target 中具有不同有效调用边。

**为什么普通调用图不足**

以目录或最近查询 Target 给函数永久打芯片标签，会把公共源码错误归属于单一芯片；合并两个 Target 的边又会丢失条件语义。

**架构要求**

使用稳定 Source Entity，并以 Target occurrence 连接具体编译视角。领域标签和 occurrence 都必须带来源，二者不能相互覆盖。

**代码—领域知识链接要求**

Function—Feature 或 Function—Chip 链接应允许多值、Target 约束和 `verified/inferred/manual` 区分；重新索引不能静默覆盖人工知识。

**当前研究不声称**

不预设这些关系必须存放在图数据库中。

## W08 — 同名函数与日志入口需要消歧

**问题模式**

不同芯片目录中存在同名 Device 函数和相同日志字符串。仅按函数名或字符串返回单个结果会误导 Target 选择。

**代码证据**

- `device/wifi/chip2/hcc/hcc_device.c:79-107` 与 `device/wifi/chip8/hcc/hcc_device.c:79-107`：两个文件都定义 `hcc_device_rx_handler`，并包含相同 `[HCC_DEVICE] RX` 日志。
- `device/wifi/chip2/frw/frw_event.c:15` 与 `device/wifi/chip8/frw/frw_event.c:12`：两个芯片目录都定义 `frw_event_dispatch`。
- `host/platform/main/platform_main.c:31-46`：`platform_init` 日志定位后仍需结合调用上下文和 Target。

```c
int hcc_device_rx_handler(void *data, uint32_t length)
{
    printf("[HCC_DEVICE] RX: channel=%d, msg_type=%d, length=%d\n", ...);
}
```

**为什么普通调用图不足**

名称匹配不提供 repository、file、signature、occurrence 和 Target。日志检索能找到入口候选，但不能自动决定当前设备芯片。

**架构要求**

代码实体 ID 至少包含 repository/revision、file、symbol/signature 或 occurrence；搜索返回候选列表和 Target presence，不自动挑选。

**代码—领域知识链接要求**

日志说明、故障手册和 Known Edge Case 应链接到消歧后的代码实体及适用 Target，并在源码移动或日志变更后重新验证。

**当前研究不声称**

不把日志相似度或同名符号视为确定身份关系。

## 2. 从案例导出的架构评价维度

| 维度 | 来源案例 | 需要回答的问题 |
|---|---|---|
| Target correctness | W01-W04、W07 | 事实是否对应真实编译视角，互斥边是否被合并 |
| 间接调用与候选表达 | W05 | 是否保留赋值、选择条件、候选和 abstention |
| 跨 Host/Device Event | W06 | 是否用协议实体连接独立编译视角并保留多候选 |
| 代码实体身份 | W07-W08 | 是否区分源码身份、Target occurrence、同名符号和路径 |
| 代码—领域知识链接 | W03-W08 | 链接是否有 Target/revision、provenance、confidence 和失效策略 |
| Agent 上下文控制 | W01-W08 | 是否支持摘要、limit、分页和按需源码，而非一次加载全图 |

这些维度用于筛选成熟方案和设计后续 Benchmark，不在当前案例集内打分。
