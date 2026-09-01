#ifndef OBMM_H
#define OBMM_H

#include <stdint.h>
#include <stddef.h>
#include "urma.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct obmm_client obmm_client_t;
typedef struct obmm_pool_handle obmm_pool_handle_t;

struct obmm_client {
    urma_context_t *urma_ctx;
    uint16_t node_id;
};

struct obmm_pool_handle {
    obmm_client_t *client;
    uint32_t pool_id;
    uint16_t owner_node;
    uint32_t remote_seg_id;
    uint32_t token_id;
    size_t size;
    urma_jetty_t *jetty;
    urma_segment_t *local_cache_seg;
};

/* Official OBMM C Library Functions */
obmm_client_t *obmm_init(urma_context_t *urma_ctx);
void obmm_destroy(obmm_client_t *client);

uint32_t obmm_export_pool(obmm_client_t *client, void *buffer, size_t size, uint32_t token_id, uint32_t permissions);

obmm_pool_handle_t *obmm_import_pool(obmm_client_t *client, uint16_t owner_node, uint32_t pool_id, size_t size, uint32_t token_id);
void obmm_release_pool(obmm_pool_handle_t *handle);

int obmm_pool_write(obmm_pool_handle_t *handle, size_t offset, const void *src, size_t size, double *out_latency_ns);
int obmm_pool_read(obmm_pool_handle_t *handle, size_t offset, void *dst, size_t size, double *out_latency_ns);

#ifdef __cplusplus
}
#endif

#endif /* OBMM_H */
