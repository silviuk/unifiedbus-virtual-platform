#ifndef UNIFIEDBUS_UBUS_H
#define UNIFIEDBUS_UBUS_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define UB_PCI_VENDOR_ID        0x19E5  /* Huawei / openEuler vendor space */
#define UB_PCI_DEVICE_ID        0xA880  /* UnifiedBus Controller */

/* UB Hardware BAR 0 Register Map */
#define UB_REG_MAGIC            0x00    /* Read: 'UBUS' (0x53554255) */
#define UB_REG_VERSION          0x04    /* Protocol Version (e.g. 0x0200 = 2.0) */
#define UB_REG_NODE_ID          0x08    /* Local Node ID */
#define UB_REG_LINK_STATUS      0x0C    /* 1 = UP, 0 = DOWN */
#define UB_REG_LINK_SPEED_GBPS  0x10    /* e.g. 800 Gbps */
#define UB_REG_INTERRUPT_MASK   0x14    /* MSI-X Interrupt Enable/Mask */
#define UB_REG_DOORBELL         0x18    /* Trigger hardware command processing */
#define UB_REG_STATUS           0x1C    /* Controller Status */

/* UMMU Global Page Table Base Register in BAR 1 */
#define UB_REG_UMMU_CR0         0x00    /* UMMU Control */
#define UB_REG_UMMU_TTBR0       0x08    /* Translation Table Base Register */
#define UB_REG_UMMU_TOKEN_ID    0x10    /* Current Security Token */

/* Descriptor Header */
typedef struct __attribute__((packed)) {
    uint16_t opcode;
    uint16_t flags;
    uint32_t seq_num;
    uint16_t src_node;
    uint16_t dst_node;
    uint32_t token_id;
    uint64_t src_addr;
    uint64_t dst_addr;
    uint32_t length;
    uint32_t status;
} ub_descriptor_t;

/* ACPI UBRT (UnifiedBus Root Table) structure */
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
} ubrt_table_t;

#ifdef __cplusplus
}
#endif

#endif /* UNIFIEDBUS_UBUS_H */
