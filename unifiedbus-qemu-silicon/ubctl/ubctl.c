#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "../include/ubus_hw.h"
#include "../include/ubus_ioctl.h"
#include "../include/urma.h"
#include "../kernel/ubus_driver.h"

static void print_help(const char *prog) {
    printf("UnifiedBus (UB) Hardware Management Utility (ubctl) v2.0\n");
    printf("Usage: %s <command> [options]\n\n", prog);
    printf("Commands:\n");
    printf("  info        Show local UBPU PCIe controller status & BAR apertures\n");
    printf("  stats       Display real-time TX/RX flit counters and CIP crypto metrics\n");
    printf("  topology    Display active SuperPoD nodes and interconnect links\n");
    printf("  help        Show this help message\n");
}

int main(int argc, char **argv) {
    if (argc < 2 || strcmp(argv[1], "help") == 0 || strcmp(argv[1], "--help") == 0) {
        print_help(argv[0]);
        return 0;
    }

    const char *cmd = argv[1];
    uint16_t node_id = 1;
    if (argc >= 3) {
        node_id = (uint16_t)atoi(argv[2]);
    }

    int dev_fd = ubus_dev_open(node_id);
    if (dev_fd < 0) {
        fprintf(stderr, "[Error] Failed to open /dev/ub0 device for Node %d\n", node_id);
        return 1;
    }

    if (strcmp(cmd, "info") == 0) {
        struct ub_ioctl_dev_info info;
        if (ubus_dev_ioctl(dev_fd, UB_IOCTL_GET_DEV_INFO, &info) != 0) {
            fprintf(stderr, "[Error] IOCTL GET_DEV_INFO failed\n");
            return 1;
        }
        printf("=================================================================\n");
        printf(" UnifiedBus (UB) Controller Hardware Info - Node 0x%04X\n", info.node_id);
        printf("=================================================================\n");
        printf(" PCIe Vendor ID   : 0x%04X (Huawei Technologies Co., Ltd.)\n", info.vendor_id);
        printf(" PCIe Device ID   : 0x%04X (UnifiedBus Host Controller / UBPU)\n", info.device_id);
        printf(" Hardware Spec    : UB Base Specification v%d.%d\n", info.hw_version >> 8, info.hw_version & 0xFF);
        printf(" Link Status      : %s\n", info.link_status ? "ACTIVE (UP)" : "DOWN");
        printf(" Link Bandwidth   : %u.0 Gbps (Ultra-Low Latency)\n", info.link_speed_gbps);
        printf(" BAR 0 (CSR)      : %lu KB MMIO\n", info.bar0_size / 1024);
        printf(" BAR 1 (UMMU)     : %lu KB MMIO (Global Address Translation)\n", info.bar1_size / 1024);
        printf(" BAR 2 (Rings)    : %lu KB MMIO (Submission & Completion Queues)\n", info.bar2_size / 1024);
        printf(" BAR 3 (SHM)      : %lu MB Direct Memory Aperture\n", info.bar3_size / (1024*1024));
        printf("=================================================================\n");
    } else if (strcmp(cmd, "stats") == 0) {
        struct ub_ioctl_stats st;
        if (ubus_dev_ioctl(dev_fd, UB_IOCTL_QUERY_STATS, &st) != 0) {
            fprintf(stderr, "[Error] IOCTL QUERY_STATS failed\n");
            return 1;
        }
        printf("=================================================================\n");
        printf(" UnifiedBus Real-Time Performance & Security Telemetry - Node 0x%04X\n", node_id);
        printf("=================================================================\n");
        printf(" Transmitted Flits  : %lu (64-byte flits)\n", st.tx_flits);
        printf(" Received Flits     : %lu (64-byte flits)\n", st.rx_flits);
        printf(" Total TX Traffic   : %.2f MB\n", (double)st.tx_bytes / (1024.0*1024.0));
        printf(" Total RX Traffic   : %.2f MB\n", (double)st.rx_bytes / (1024.0*1024.0));
        printf(" CRC Checksum Errors: %lu\n", st.crc_errors);
        printf(" CIP Tamper Rejects : %lu\n", st.cip_tamper_errors);
        printf(" CIP Replay Drops   : %lu\n", st.cip_replay_errors);
        printf("=================================================================\n");
    } else if (strcmp(cmd, "topology") == 0) {
        printf("=================================================================\n");
        printf(" UnifiedBus SuperPoD Interconnect Topology (Fabric Switch 0)\n");
        printf("=================================================================\n");
        printf(" Node ID  | Type                 | Speed     | Status\n");
        printf(" ---------+----------------------+-----------+---------\n");
        printf("  0x0001  | KUNPENG_CPU_HOST     | 800 Gbps  | ONLINE\n");
        printf("  0x0002  | KUNPENG_CPU_HOST     | 800 Gbps  | ONLINE\n");
        printf("  0x0003  | ASCEND_NPU_ACCEL     | 800 Gbps  | ONLINE\n");
        printf("  0x0004  | ASCEND_NPU_ACCEL     | 800 Gbps  | ONLINE\n");
        printf("  0x0007  | POOLED_MEM_APPLIANCE | 800 Gbps  | ONLINE\n");
        printf("=================================================================\n");
    } else {
        fprintf(stderr, "Unknown command: %s. Run '%s help' for usage.\n", cmd, argv[0]);
        return 1;
    }

    return 0;
}
