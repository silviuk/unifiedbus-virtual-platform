#ifndef UB_SILICON_BACKEND_H
#define UB_SILICON_BACKEND_H

#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>
#include <pthread.h>
#include "../include/ubus_hw.h"

#define MAX_NODES 64
#define MAX_SEGMENTS_PER_NODE 256
#define MAX_JETTIES_PER_NODE 512
#define NODE_MEM_SIZE (64 * 1024 * 1024) /* 64 MB hardware RAM aperture per node */

typedef struct {
    uint32_t segment_id;
    uint32_t token_id;
    uint64_t base_offset;
    uint64_t size;
    uint32_t permissions; /* 1=R, 2=W, 3=RW */
    bool valid;
} ub_silicon_segment_t;

typedef struct {
    uint32_t jetty_id;
    uint16_t remote_node;
    uint16_t remote_jetty_id;
    uint32_t token_id;
    bool valid;
} ub_silicon_jetty_t;

typedef struct {
    uint16_t node_id;
    char node_type[32];
    uint8_t memory[NODE_MEM_SIZE];
    ub_silicon_segment_t segments[MAX_SEGMENTS_PER_NODE];
    ub_silicon_jetty_t jetties[MAX_JETTIES_PER_NODE];
    uint64_t tx_flits;
    uint64_t rx_flits;
    uint64_t tx_bytes;
    uint64_t rx_bytes;
    uint64_t crc_errors;
    uint64_t cip_tamper_errors;
    uint64_t cip_replay_errors;
    uint32_t cip_cipher_suite;
    bool link_up;
    pthread_mutex_t lock;
} ub_silicon_node_t;

typedef struct {
    ub_silicon_node_t nodes[MAX_NODES];
    double link_bw_gbps;
    double hop_latency_ns;
    pthread_mutex_t fabric_lock;
} ub_silicon_fabric_t;

/* Silicon Backend Lifecycle & Operations */
ub_silicon_fabric_t *ub_silicon_fabric_init(double bw_gbps, double hop_latency_ns);
void ub_silicon_fabric_destroy(ub_silicon_fabric_t *fabric);

int ub_silicon_register_node(ub_silicon_fabric_t *fabric, uint16_t node_id, const char *node_type);
int ub_silicon_unregister_node(ub_silicon_fabric_t *fabric, uint16_t node_id);

int ub_silicon_register_segment(ub_silicon_fabric_t *fabric, uint16_t node_id, uint32_t seg_id,
                               uint64_t offset, uint64_t size, uint32_t token_id, uint32_t perm);

int ub_silicon_create_jetty(ub_silicon_fabric_t *fabric, uint16_t src_node, uint32_t local_jetty_id,
                            uint16_t dst_node, uint32_t dst_jetty_id, uint32_t token_id);

int ub_silicon_process_wr(ub_silicon_fabric_t *fabric, uint16_t src_node, ub_hw_descriptor_t *desc,
                          const uint8_t *in_payload, uint8_t *out_payload, double *out_lat_ns, char *err_buf, size_t err_len);

#endif /* UB_SILICON_BACKEND_H */
