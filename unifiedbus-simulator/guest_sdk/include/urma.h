#ifndef UNIFIEDBUS_URMA_H
#define UNIFIEDBUS_URMA_H

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct urma_context* urma_ctx_t;
typedef struct urma_segment* urma_seg_t;
typedef struct urma_jetty*   urma_jetty_t;

typedef enum {
    URMA_ACCESS_READ  = (1 << 0),
    URMA_ACCESS_WRITE = (1 << 1),
    URMA_ACCESS_ATOMIC= (1 << 2)
} urma_access_flags_t;

/* Initialize URMA context for node */
urma_ctx_t urma_init(uint16_t node_id, const char* socket_path);

/* Register memory segment for RDMA */
urma_seg_t urma_register_segment(urma_ctx_t ctx, void* addr, size_t length, uint32_t token_id, uint32_t access_flags);

/* Create communication Jetty endpoint */
urma_jetty_t urma_create_jetty(urma_ctx_t ctx, uint16_t remote_node, uint32_t remote_jetty_id, uint32_t token_id);

/* Post RDMA Write operation */
int urma_post_write(urma_jetty_t jetty, urma_seg_t local_seg, size_t local_offset, uint32_t remote_seg_id, size_t remote_offset, size_t len);

/* Post RDMA Read operation */
int urma_post_read(urma_jetty_t jetty, urma_seg_t local_seg, size_t local_offset, uint32_t remote_seg_id, size_t remote_offset, size_t len);

/* Close and cleanup */
void urma_close(urma_ctx_t ctx);

#ifdef __cplusplus
}
#endif

#endif /* UNIFIEDBUS_URMA_H */
