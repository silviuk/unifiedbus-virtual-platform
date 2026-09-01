#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "../../include/urma.h"
#include "../../include/ubus_ioctl.h"
#include "../../kernel/ubus_driver.h"

urma_context_t *urma_open_device(const char *dev_path, uint16_t node_id) {
    urma_context_t *ctx = (urma_context_t *)calloc(1, sizeof(urma_context_t));
    if (!ctx) return NULL;

    ctx->node_id = node_id;
    ctx->dev_fd = ubus_dev_open(node_id);
    if (ctx->dev_fd < 0) {
        free(ctx);
        return NULL;
    }

    struct ub_ioctl_dev_info info;
    if (ubus_dev_ioctl(ctx->dev_fd, UB_IOCTL_GET_DEV_INFO, &info) == 0) {
        ctx->link_speed_gbps = info.link_speed_gbps;
    }
    return ctx;
}

void urma_close_device(urma_context_t *ctx) {
    if (!ctx) return;
    if (ctx->dev_fd >= 0) {
        ubus_dev_close(ctx->dev_fd);
    }
    free(ctx);
}

urma_segment_t *urma_register_segment(urma_context_t *ctx, void *buffer, size_t size, uint32_t token_id, uint32_t permissions) {
    if (!ctx || !buffer || size == 0) return NULL;

    struct ub_ioctl_reg_seg reg;
    reg.user_vaddr = (uint64_t)buffer;
    reg.size = size;
    reg.token_id = token_id;
    reg.permissions = permissions;

    if (ubus_dev_ioctl(ctx->dev_fd, UB_IOCTL_REG_SEG, &reg) != 0) {
        return NULL;
    }

    urma_segment_t *seg = (urma_segment_t *)malloc(sizeof(urma_segment_t));
    if (!seg) return NULL;

    seg->segment_id = reg.segment_id;
    seg->token_id = token_id;
    seg->user_buffer = buffer;
    seg->size = size;
    seg->permissions = permissions;
    return seg;
}

int urma_unregister_segment(urma_context_t *ctx, urma_segment_t *seg) {
    if (!ctx || !seg) return -1;
    struct ub_ioctl_unreg_seg unreg;
    unreg.segment_id = seg->segment_id;
    int ret = ubus_dev_ioctl(ctx->dev_fd, UB_IOCTL_UNREG_SEG, &unreg);
    free(seg);
    return ret;
}

urma_jetty_t *urma_create_jetty(urma_context_t *ctx, uint16_t remote_node, uint16_t remote_jetty_id, uint32_t token_id) {
    if (!ctx) return NULL;

    struct ub_ioctl_create_jetty cj;
    cj.remote_node = remote_node;
    cj.remote_jetty_id = remote_jetty_id;
    cj.token_id = token_id;

    if (ubus_dev_ioctl(ctx->dev_fd, UB_IOCTL_CREATE_JETTY, &cj) != 0) {
        return NULL;
    }

    urma_jetty_t *j = (urma_jetty_t *)malloc(sizeof(urma_jetty_t));
    if (!j) return NULL;

    j->ctx = ctx;
    j->jetty_id = cj.jetty_id;
    j->remote_node = remote_node;
    j->remote_jetty_id = remote_jetty_id;
    j->token_id = token_id;
    return j;
}

int urma_destroy_jetty(urma_jetty_t *jetty) {
    if (!jetty) return -1;
    struct ub_ioctl_destroy_jetty dj;
    dj.jetty_id = jetty->jetty_id;
    int ret = ubus_dev_ioctl(jetty->ctx->dev_fd, UB_IOCTL_DESTROY_JETTY, &dj);
    free(jetty);
    return ret;
}

int urma_write(urma_jetty_t *jetty, urma_segment_t *local_seg, size_t local_offset,
               uint32_t remote_seg_id, size_t remote_offset, size_t length, double *out_latency_ns) {
    if (!jetty || !local_seg || local_offset + length > local_seg->size) return -1;

    struct ub_ioctl_submit_wr wr;
    memset(&wr, 0, sizeof(wr));
    wr.jetty_id = jetty->jetty_id;
    wr.opcode = 0x60; /* URMA Write */
    wr.local_seg_id = local_seg->segment_id;
    wr.local_offset = (uint64_t)((char*)local_seg->user_buffer + local_offset);
    wr.remote_seg_id = remote_seg_id;
    wr.remote_offset = remote_offset;
    wr.length = length;

    int ret = ubus_dev_ioctl(jetty->ctx->dev_fd, UB_IOCTL_SUBMIT_WR, &wr);
    if (ret == 0 && out_latency_ns) {
        *out_latency_ns = wr.sim_latency_ns;
    }
    return ret;
}

int urma_read(urma_jetty_t *jetty, urma_segment_t *local_seg, size_t local_offset,
              uint32_t remote_seg_id, size_t remote_offset, size_t length, double *out_latency_ns) {
    if (!jetty || !local_seg || local_offset + length > local_seg->size) return -1;

    struct ub_ioctl_submit_wr wr;
    memset(&wr, 0, sizeof(wr));
    wr.jetty_id = jetty->jetty_id;
    wr.opcode = 0x62; /* URMA Read */
    wr.local_seg_id = local_seg->segment_id;
    wr.local_offset = (uint64_t)((char*)local_seg->user_buffer + local_offset);
    wr.remote_seg_id = remote_seg_id;
    wr.remote_offset = remote_offset;
    wr.length = length;

    int ret = ubus_dev_ioctl(jetty->ctx->dev_fd, UB_IOCTL_SUBMIT_WR, &wr);
    if (ret == 0 && out_latency_ns) {
        *out_latency_ns = wr.sim_latency_ns;
    }
    return ret;
}

int urma_atomic_cas(urma_jetty_t *jetty, uint32_t remote_seg_id, size_t remote_offset,
                    uint64_t compare_val, uint64_t swap_val, uint64_t *out_orig_val, double *out_latency_ns) {
    if (!jetty) return -1;

    struct ub_ioctl_submit_wr wr;
    memset(&wr, 0, sizeof(wr));
    wr.jetty_id = jetty->jetty_id;
    wr.opcode = 0x67; /* CAS */
    wr.remote_seg_id = remote_seg_id;
    wr.remote_offset = remote_offset;
    wr.compare_val = compare_val;
    wr.swap_val = swap_val;
    wr.length = 8;

    int ret = ubus_dev_ioctl(jetty->ctx->dev_fd, UB_IOCTL_SUBMIT_WR, &wr);
    if (ret == 0) {
        if (out_orig_val) *out_orig_val = wr.orig_val;
        if (out_latency_ns) *out_latency_ns = wr.sim_latency_ns;
    }
    return ret;
}

int urma_atomic_add(urma_jetty_t *jetty, uint32_t remote_seg_id, size_t remote_offset,
                    uint64_t add_val, uint64_t *out_orig_val, double *out_latency_ns) {
    if (!jetty) return -1;

    struct ub_ioctl_submit_wr wr;
    memset(&wr, 0, sizeof(wr));
    wr.jetty_id = jetty->jetty_id;
    wr.opcode = 0x68; /* Add */
    wr.remote_seg_id = remote_seg_id;
    wr.remote_offset = remote_offset;
    wr.swap_val = add_val;
    wr.length = 8;

    int ret = ubus_dev_ioctl(jetty->ctx->dev_fd, UB_IOCTL_SUBMIT_WR, &wr);
    if (ret == 0) {
        if (out_orig_val) *out_orig_val = wr.orig_val;
        if (out_latency_ns) *out_latency_ns = wr.sim_latency_ns;
    }
    return ret;
}

/* Sender-side CIP software/hardware transform */
static void cip_client_encrypt(const uint8_t *in, uint8_t *out, size_t len, uint32_t token_id) {
    uint8_t key_seed = (uint8_t)((token_id ^ (token_id >> 8)) & 0xFF);
    for (size_t i = 0; i < len; i++) {
        out[i] = in[i] ^ (key_seed + (uint8_t)(i * 31));
    }
}

int urma_write_encrypted_cip(urma_jetty_t *jetty, urma_segment_t *local_seg, size_t local_offset,
                             uint32_t remote_seg_id, size_t remote_offset, size_t length, double *out_latency_ns) {
    if (!jetty || !local_seg) return -1;

    uint8_t *cipher_buf = (uint8_t *)malloc(length);
    cip_client_encrypt((const uint8_t *)((char*)local_seg->user_buffer + local_offset), cipher_buf, length, jetty->token_id);

    struct ub_ioctl_submit_wr wr;
    memset(&wr, 0, sizeof(wr));
    wr.jetty_id = jetty->jetty_id;
    wr.opcode = 0x60;
    wr.flags = 0x80; /* FLAG_CIP_ENCRYPTED */
    wr.local_seg_id = local_seg->segment_id;
    wr.local_offset = (uint64_t)cipher_buf;
    wr.remote_seg_id = remote_seg_id;
    wr.remote_offset = remote_offset;
    wr.length = length;

    int ret = ubus_dev_ioctl(jetty->ctx->dev_fd, UB_IOCTL_SUBMIT_WR, &wr);
    if (ret == 0 && out_latency_ns) {
        *out_latency_ns = wr.sim_latency_ns;
    }
    free(cipher_buf);
    return ret;
}
