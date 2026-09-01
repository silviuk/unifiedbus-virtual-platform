#ifndef UBUS_HW_H
#define UBUS_HW_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* PCIe Hardware Identification (Huawei / openEuler UnifiedBus Controller) */
#define UB_PCI_VENDOR_ID        0x19E5  /* Huawei Technologies Co., Ltd. */
#define UB_PCI_DEVICE_ID        0xA880  /* UnifiedBus Host Controller / UBPU */
#define UB_PCI_CLASS            0x028000/* Network / Interconnect Controller */
#define UB_HW_MAGIC             0x53554255 /* 'UBUS' in ASCII */
#define UB_HW_VERSION           0x0200  /* Version 2.0 */

/* BAR 0: Control & Status Registers (CSR) - 64 KB MMIO */
#define UB_REG_MAGIC            0x0000  /* Read-only: UB_HW_MAGIC */
#define UB_REG_VERSION          0x0004  /* Read-only: UB_HW_VERSION */
#define UB_REG_NODE_ID          0x0008  /* Read/Write: Local Node ID (1..65535) */
#define UB_REG_LINK_STATUS      0x000C  /* Read-only: 1=UP, 0=DOWN */
#define UB_REG_LINK_SPEED_GBPS  0x0010  /* Read-only: 800 (Gbps) */
#define UB_REG_INTERRUPT_MASK   0x0014  /* Read/Write: MSI-X IRQ Mask */
#define UB_REG_DOORBELL         0x0018  /* Write-only: Trigger command doorbell */
#define UB_REG_STATUS           0x001C  /* Read-only: Hardware status / error flags */
#define UB_REG_CIP_CONTROL      0x0020  /* Read/Write: CIP Security Control */
#define UB_REG_TX_FLIT_COUNT    0x0024  /* Read-only: Cumulative TX flits */
#define UB_REG_RX_FLIT_COUNT    0x0028  /* Read-only: Cumulative RX flits */

/* BAR 1: UMMU (Unified Memory Management Unit) - 1 MB MMIO */
#define UB_REG_UMMU_CR0         0x0000  /* UMMU Control Register */
#define UB_REG_UMMU_TTBR0       0x0008  /* Translation Table Base Register */
#define UB_REG_UMMU_SEG_COUNT   0x0010  /* Number of registered segments */
#define UB_REG_UMMU_TOKEN_ID    0x0014  /* Current Security Token */
#define UB_REG_UMMU_ENTRY_BASE  0x0100  /* Base offset for hardware segment descriptors */

/* BAR 2: Hardware Queue Doorbell & Rings - 256 KB MMIO */
#define UB_REG_SQ_HEAD          0x0000  /* Submission Queue Head */
#define UB_REG_SQ_TAIL          0x0004  /* Submission Queue Tail */
#define UB_REG_CQ_HEAD          0x0008  /* Completion Queue Head */
#define UB_REG_CQ_TAIL          0x000C  /* Completion Queue Tail */
#define UB_REG_RING_DOORBELL    0x0010  /* Ring buffer doorbell trigger */

/* Hardware Segment Descriptor in UMMU Table (32 bytes) */
typedef struct __attribute__((packed)) {
    uint32_t segment_id;
    uint32_t token_id;
    uint64_t base_addr;
    uint64_t size;
    uint32_t permissions; /* 1=R, 2=W, 3=RW */
    uint32_t flags;
} ub_hw_segment_desc_t;

/* Hardware DMA / URMA Work Request Descriptor (48 bytes) */
typedef struct __attribute__((packed)) {
    uint16_t opcode;
    uint16_t flags;
    uint32_t seq_num;
    uint16_t src_node;
    uint16_t dst_node;
    uint32_t token_id;
    uint64_t src_offset;
    uint64_t dst_offset;
    uint32_t length;
    uint32_t remote_seg_id;
    uint32_t local_seg_id;
    uint32_t status;      /* Output status code */
} ub_hw_descriptor_t;

/* ACPI UBRT Table definition */
typedef struct __attribute__((packed)) {
    char signature[4];        /* "UBRT" */
    uint32_t length;
    uint8_t revision;
    uint8_t checksum;
    char oem_id[6];
    char oem_table_id[8];
    uint32_t oem_revision;
    uint32_t creator_id;
    uint32_t creator_revision;
    uint32_t num_controllers;
    uint64_t mmio_base;
    uint64_t mmio_size;
} ubrt_acpi_table_t;

#ifdef __cplusplus
}
#endif

#endif /* UBUS_HW_H */
