#ifndef UBUS_IOCTL_H
#define UBUS_IOCTL_H

#include <stdint.h>
#include <sys/ioctl.h>

#ifdef __cplusplus
extern "C" {
#endif

#define UBUS_IOCTL_MAGIC 'U'

/* IOCTL Command Codes */
#define UB_IOCTL_GET_DEV_INFO    _IOR(UBUS_IOCTL_MAGIC, 0x01, struct ub_ioctl_dev_info)
#define UB_IOCTL_REG_SEG         _IOWR(UBUS_IOCTL_MAGIC, 0x02, struct ub_ioctl_reg_seg)
#define UB_IOCTL_UNREG_SEG       _IOW(UBUS_IOCTL_MAGIC, 0x03, struct ub_ioctl_unreg_seg)
#define UB_IOCTL_CREATE_JETTY    _IOWR(UBUS_IOCTL_MAGIC, 0x04, struct ub_ioctl_create_jetty)
#define UB_IOCTL_DESTROY_JETTY   _IOW(UBUS_IOCTL_MAGIC, 0x05, struct ub_ioctl_destroy_jetty)
#define UB_IOCTL_SUBMIT_WR       _IOWR(UBUS_IOCTL_MAGIC, 0x06, struct ub_ioctl_submit_wr)
#define UB_IOCTL_POLL_CQ         _IOWR(UBUS_IOCTL_MAGIC, 0x07, struct ub_ioctl_poll_cq)
#define UB_IOCTL_SET_CIP_CONFIG  _IOW(UBUS_IOCTL_MAGIC, 0x08, struct ub_ioctl_cip_config)
#define UB_IOCTL_QUERY_STATS     _IOR(UBUS_IOCTL_MAGIC, 0x09, struct ub_ioctl_stats)

/* Structures passed via IOCTL */
struct ub_ioctl_dev_info {
    uint16_t node_id;
    uint16_t vendor_id;
    uint16_t device_id;
    uint16_t hw_version;
    uint32_t link_status;      /* 1 = UP */
    uint32_t link_speed_gbps;  /* e.g. 800 */
    uint64_t bar0_size;
    uint64_t bar1_size;
    uint64_t bar2_size;
    uint64_t bar3_size;
};

struct ub_ioctl_reg_seg {
    uint64_t user_vaddr;       /* Virtual address of user buffer */
    uint64_t size;             /* Size in bytes */
    uint32_t token_id;         /* Security Token */
    uint32_t permissions;      /* 1=R, 2=W, 3=RW */
    uint32_t segment_id;       /* Returned hardware Segment ID */
};

struct ub_ioctl_unreg_seg {
    uint32_t segment_id;
};

struct ub_ioctl_create_jetty {
    uint16_t remote_node;
    uint16_t remote_jetty_id;
    uint32_t token_id;
    uint32_t jetty_id;         /* Returned allocated Jetty ID */
};

struct ub_ioctl_destroy_jetty {
    uint32_t jetty_id;
};

struct ub_ioctl_submit_wr {
    uint32_t jetty_id;
    uint16_t opcode;           /* 0x60=Write, 0x62=Read, 0x67=CAS, 0x68=Add */
    uint16_t flags;            /* 0x80=CIP Encrypted */
    uint32_t local_seg_id;
    uint64_t local_offset;
    uint32_t remote_seg_id;
    uint64_t remote_offset;
    uint32_t length;
    uint64_t compare_val;      /* For CAS */
    uint64_t swap_val;         /* For CAS / Swap / Add */
    uint64_t orig_val;         /* Returned for Atomics */
    double   sim_latency_ns;   /* Returned simulated hardware latency */
};

struct ub_ioctl_poll_cq {
    uint32_t cq_id;
    uint32_t num_entries;
    uint32_t completed_count;
};

struct ub_ioctl_cip_config {
    uint32_t cipher_suite;     /* 1=AES-128-GCM, 2=AES-256-GCM, 3=SM4-GCM */
    uint32_t enable_anti_replay;
};

struct ub_ioctl_stats {
    uint64_t tx_packets;
    uint64_t rx_packets;
    uint64_t tx_flits;
    uint64_t rx_flits;
    uint64_t tx_bytes;
    uint64_t rx_bytes;
    uint64_t crc_errors;
    uint64_t cip_tamper_errors;
    uint64_t cip_replay_errors;
};

#ifdef __cplusplus
}
#endif

#endif /* UBUS_IOCTL_H */
