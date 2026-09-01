#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "ub_silicon_backend.h"

#define FLIT_SIZE 64

ub_silicon_fabric_t *ub_silicon_fabric_init(double bw_gbps, double hop_latency_ns) {
    ub_silicon_fabric_t *fabric = (ub_silicon_fabric_t *)calloc(1, sizeof(ub_silicon_fabric_t));
    if (!fabric) return NULL;

    fabric->link_bw_gbps = (bw_gbps > 0) ? bw_gbps : 800.0;
    fabric->hop_latency_ns = (hop_latency_ns > 0) ? hop_latency_ns : 15.0;
    pthread_mutex_init(&fabric->fabric_lock, NULL);

    for (int i = 0; i < MAX_NODES; i++) {
        pthread_mutex_init(&fabric->nodes[i].lock, NULL);
    }
    return fabric;
}

void ub_silicon_fabric_destroy(ub_silicon_fabric_t *fabric) {
    if (!fabric) return;
    for (int i = 0; i < MAX_NODES; i++) {
        pthread_mutex_destroy(&fabric->nodes[i].lock);
    }
    pthread_mutex_destroy(&fabric->fabric_lock);
    free(fabric);
}

int ub_silicon_register_node(ub_silicon_fabric_t *fabric, uint16_t node_id, const char *node_type) {
    if (!fabric || node_id >= MAX_NODES) return -1;
    pthread_mutex_lock(&fabric->fabric_lock);

    ub_silicon_node_t *node = &fabric->nodes[node_id];
    pthread_mutex_lock(&node->lock);

    node->node_id = node_id;
    strncpy(node->node_type, node_type ? node_type : "KUNPENG_CPU", sizeof(node->node_type) - 1);
    node->link_up = true;
    node->cip_cipher_suite = 2; /* AES-256-GCM default */

    pthread_mutex_unlock(&node->lock);
    pthread_mutex_unlock(&fabric->fabric_lock);
    return 0;
}

int ub_silicon_unregister_node(ub_silicon_fabric_t *fabric, uint16_t node_id) {
    if (!fabric || node_id >= MAX_NODES) return -1;
    pthread_mutex_lock(&fabric->fabric_lock);

    ub_silicon_node_t *node = &fabric->nodes[node_id];
    pthread_mutex_lock(&node->lock);
    node->link_up = false;
    memset(node->segments, 0, sizeof(node->segments));
    memset(node->jetties, 0, sizeof(node->jetties));
    pthread_mutex_unlock(&node->lock);

    pthread_mutex_unlock(&fabric->fabric_lock);
    return 0;
}

int ub_silicon_register_segment(ub_silicon_fabric_t *fabric, uint16_t node_id, uint32_t seg_id,
                               uint64_t offset, uint64_t size, uint32_t token_id, uint32_t perm) {
    if (!fabric || node_id >= MAX_NODES || seg_id >= MAX_SEGMENTS_PER_NODE) return -1;
    ub_silicon_node_t *node = &fabric->nodes[node_id];

    pthread_mutex_lock(&node->lock);
    node->segments[seg_id].segment_id = seg_id;
    node->segments[seg_id].token_id = token_id;
    node->segments[seg_id].base_offset = offset;
    node->segments[seg_id].size = size;
    node->segments[seg_id].permissions = perm;
    node->segments[seg_id].valid = true;
    pthread_mutex_unlock(&node->lock);
    return 0;
}

int ub_silicon_create_jetty(ub_silicon_fabric_t *fabric, uint16_t src_node, uint32_t local_jetty_id,
                            uint16_t dst_node, uint32_t dst_jetty_id, uint32_t token_id) {
    if (!fabric || src_node >= MAX_NODES || local_jetty_id >= MAX_JETTIES_PER_NODE) return -1;
    ub_silicon_node_t *node = &fabric->nodes[src_node];

    pthread_mutex_lock(&node->lock);
    node->jetties[local_jetty_id].jetty_id = local_jetty_id;
    node->jetties[local_jetty_id].remote_node = dst_node;
    node->jetties[local_jetty_id].remote_jetty_id = dst_jetty_id;
    node->jetties[local_jetty_id].token_id = token_id;
    node->jetties[local_jetty_id].valid = true;
    pthread_mutex_unlock(&node->lock);
    return 0;
}

/* Simple constant-time XOR keystream simulation for CIP */
static void cip_crypto_transform(const uint8_t *in, uint8_t *out, size_t len, uint32_t token_id) {
    uint8_t key_seed = (uint8_t)((token_id ^ (token_id >> 8)) & 0xFF);
    for (size_t i = 0; i < len; i++) {
        out[i] = in[i] ^ (key_seed + (uint8_t)(i * 31));
    }
}

int ub_silicon_process_wr(ub_silicon_fabric_t *fabric, uint16_t src_node, ub_hw_descriptor_t *desc,
                          const uint8_t *in_payload, uint8_t *out_payload, double *out_lat_ns, char *err_buf, size_t err_len) {
    if (!fabric || !desc || src_node >= MAX_NODES || desc->dst_node >= MAX_NODES) {
        if (err_buf) snprintf(err_buf, err_len, "Invalid node ID");
        return -1;
    }

    ub_silicon_node_t *src = &fabric->nodes[src_node];
    ub_silicon_node_t *dst = &fabric->nodes[desc->dst_node];

    if (!dst->link_up) {
        if (err_buf) snprintf(err_buf, err_len, "Destination Node %d is offline", desc->dst_node);
        return -2;
    }

    /* UMMU Segment & TokenID Validation */
    pthread_mutex_lock(&dst->lock);
    uint32_t r_seg_id = desc->remote_seg_id;
    if (r_seg_id >= MAX_SEGMENTS_PER_NODE || !dst->segments[r_seg_id].valid) {
        pthread_mutex_unlock(&dst->lock);
        if (err_buf) snprintf(err_buf, err_len, "Remote segment %u not registered on Node %u", r_seg_id, desc->dst_node);
        return -3;
    }

    ub_silicon_segment_t *r_seg = &dst->segments[r_seg_id];
    if (desc->dst_offset + desc->length > r_seg->size) {
        pthread_mutex_unlock(&dst->lock);
        if (err_buf) snprintf(err_buf, err_len, "Out of bounds: offset=%lu length=%u segment_size=%lu",
                              desc->dst_offset, desc->length, r_seg->size);
        return -4;
    }

    /* TokenID Permission Verification */
    if (desc->token_id != 0 && r_seg->token_id != 0 && desc->token_id != r_seg->token_id) {
        pthread_mutex_unlock(&dst->lock);
        if (err_buf) snprintf(err_buf, err_len, "Permission denied: TokenID mismatch (0x%X != 0x%X)",
                              desc->token_id, r_seg->token_id);
        return -5;
    }

    uint64_t target_mem_addr = r_seg->base_offset + desc->dst_offset;
    if (target_mem_addr + desc->length > NODE_MEM_SIZE) {
        pthread_mutex_unlock(&dst->lock);
        if (err_buf) snprintf(err_buf, err_len, "Hardware RAM capacity exceeded");
        return -6;
    }

    /* Execute Operation */
    uint16_t op = desc->opcode;
    if (op == 0x60 || op == 0x70) { /* URMA Write / CDMA Write */
        if (desc->flags & 0x80) { /* CIP Encrypted */
            /* Decrypt into destination hardware RAM */
            cip_crypto_transform(in_payload, &dst->memory[target_mem_addr], desc->length, desc->token_id);
        } else {
            memcpy(&dst->memory[target_mem_addr], in_payload, desc->length);
        }
    } else if (op == 0x62) { /* URMA Read */
        if (out_payload) {
            memcpy(out_payload, &dst->memory[target_mem_addr], desc->length);
        }
    } else if (op == 0x67) { /* URMA Atomic CAS */
        uint64_t cur_val = *(uint64_t*)&dst->memory[target_mem_addr];
        desc->status = (uint32_t)cur_val;
        if (cur_val == desc->src_offset) { /* compare_val stored in src_offset */
            *(uint64_t*)&dst->memory[target_mem_addr] = desc->dst_offset; /* swap_val in dst_offset */
        }
    } else if (op == 0x68) { /* URMA Atomic Add */
        uint64_t cur_val = *(uint64_t*)&dst->memory[target_mem_addr];
        desc->status = (uint32_t)cur_val;
        *(uint64_t*)&dst->memory[target_mem_addr] = cur_val + desc->dst_offset;
    }

    pthread_mutex_unlock(&dst->lock);

    /* Update Telemetry & Timings */
    uint32_t flits = (desc->length + FLIT_SIZE - 1) / FLIT_SIZE;
    if (flits == 0) flits = 1;

    pthread_mutex_lock(&src->lock);
    src->tx_flits += flits;
    src->tx_bytes += desc->length;
    pthread_mutex_unlock(&src->lock);

    pthread_mutex_lock(&dst->lock);
    dst->rx_flits += flits;
    dst->rx_bytes += desc->length;
    pthread_mutex_unlock(&dst->lock);

    double wire_ns = (desc->length * 8.0) / fabric->link_bw_gbps;
    double mem_ns = 35.0; /* HBM3 Access latency */
    double lat = wire_ns + fabric->hop_latency_ns + mem_ns;
    if (desc->flags & 0x80) lat += 12.0; /* CIP hardware crypto pipeline */

    if (out_lat_ns) *out_lat_ns = lat;
    return 0;
}
