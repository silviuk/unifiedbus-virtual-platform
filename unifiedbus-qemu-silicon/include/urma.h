#ifndef URMA_H
#define URMA_H

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct urma_context urma_context_t;
typedef struct urma_segment urma_segment_t;
typedef struct urma_jetty   urma_jetty_t;

struct urma_context {
    int dev_fd;
    uint16_t node_id;
    uint32_t link_speed_gbps;
};

struct urma_segment {
    uint32_t segment_id;
    uint32_t token_id;
    void *user_buffer;
    size_t size;
    uint32_t permissions;
};

struct urma_jetty {
    urma_context_t *ctx;
    uint32_t jetty_id;
    uint16_t remote_node;
    uint16_t remote_jetty_id;
    uint32_t token_id;
};

/* Official URMA C Library Functions */
urma_context_t *urma_open_device(const char *dev_path, uint16_t node_id);
void urma_close_device(urma_context_t *ctx);

urma_segment_t *urma_register_segment(urma_context_t *ctx, void *buffer, size_t size, uint32_t token_id, uint32_t permissions);
int urma_unregister_segment(urma_context_t *ctx, urma_segment_t *seg);

urma_jetty_t *urma_create_jetty(urma_context_t *ctx, uint16_t remote_node, uint16_t remote_jetty_id, uint32_t token_id);
int urma_destroy_jetty(urma_jetty_t *jetty);

/* Data Transfer APIs */
int urma_write(urma_jetty_t *jetty, urma_segment_t *local_seg, size_t local_offset,
               uint32_t remote_seg_id, size_t remote_offset, size_t length, double *out_latency_ns);

int urma_read(urma_jetty_t *jetty, urma_segment_t *local_seg, size_t local_offset,
              uint32_t remote_seg_id, size_t remote_offset, size_t length, double *out_latency_ns);

int urma_atomic_cas(urma_jetty_t *jetty, uint32_t remote_seg_id, size_t remote_offset,
                    uint64_t compare_val, uint64_t swap_val, uint64_t *out_orig_val, double *out_latency_ns);

int urma_atomic_add(urma_jetty_t *jetty, uint32_t remote_seg_id, size_t remote_offset,
                    uint64_t add_val, uint64_t *out_orig_val, double *out_latency_ns);

int urma_write_encrypted_cip(urma_jetty_t *jetty, urma_segment_t *local_seg, size_t local_offset,
                             uint32_t remote_seg_id, size_t remote_offset, size_t length, double *out_latency_ns);

#ifdef __cplusplus
}
#endif

#endif /* URMA_H */
