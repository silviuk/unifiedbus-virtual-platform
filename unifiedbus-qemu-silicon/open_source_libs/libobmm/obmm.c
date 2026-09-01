#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "../../include/obmm.h"

obmm_client_t *obmm_init(urma_context_t *urma_ctx) {
    if (!urma_ctx) return NULL;
    obmm_client_t *cli = (obmm_client_t *)malloc(sizeof(obmm_client_t));
    if (!cli) return NULL;
    cli->urma_ctx = urma_ctx;
    cli->node_id = urma_ctx->node_id;
    return cli;
}

void obmm_destroy(obmm_client_t *client) {
    if (client) free(client);
}

uint32_t obmm_export_pool(obmm_client_t *client, void *buffer, size_t size, uint32_t token_id, uint32_t permissions) {
    if (!client || !buffer || size == 0) return 0;
    urma_segment_t *seg = urma_register_segment(client->urma_ctx, buffer, size, token_id, permissions);
    if (!seg) return 0;
    return seg->segment_id;
}

obmm_pool_handle_t *obmm_import_pool(obmm_client_t *client, uint16_t owner_node, uint32_t pool_id, size_t size, uint32_t token_id) {
    if (!client || size == 0) return NULL;

    obmm_pool_handle_t *handle = (obmm_pool_handle_t *)calloc(1, sizeof(obmm_pool_handle_t));
    if (!handle) return NULL;

    handle->client = client;
    handle->pool_id = pool_id;
    handle->owner_node = owner_node;
    handle->remote_seg_id = pool_id;
    handle->token_id = token_id;
    handle->size = size;

    handle->jetty = urma_create_jetty(client->urma_ctx, owner_node, 1, token_id);
    if (!handle->jetty) {
        free(handle);
        return NULL;
    }

    void *cache_buf = malloc(1024 * 1024); /* 1MB local staging window */
    handle->local_cache_seg = urma_register_segment(client->urma_ctx, cache_buf, 1024 * 1024, token_id, 3);
    return handle;
}

void obmm_release_pool(obmm_pool_handle_t *handle) {
    if (!handle) return;
    if (handle->local_cache_seg) {
        free(handle->local_cache_seg->user_buffer);
        urma_unregister_segment(handle->client->urma_ctx, handle->local_cache_seg);
    }
    if (handle->jetty) {
        urma_destroy_jetty(handle->jetty);
    }
    free(handle);
}

int obmm_pool_write(obmm_pool_handle_t *handle, size_t offset, const void *src, size_t size, double *out_latency_ns) {
    if (!handle || !src || offset + size > handle->size) return -1;
    memcpy(handle->local_cache_seg->user_buffer, src, size);
    return urma_write(handle->jetty, handle->local_cache_seg, 0, handle->remote_seg_id, offset, size, out_latency_ns);
}

int obmm_pool_read(obmm_pool_handle_t *handle, size_t offset, void *dst, size_t size, double *out_latency_ns) {
    if (!handle || !dst || offset + size > handle->size) return -1;
    int ret = urma_read(handle->jetty, handle->local_cache_seg, 0, handle->remote_seg_id, offset, size, out_latency_ns);
    if (ret == 0) {
        memcpy(dst, handle->local_cache_seg->user_buffer, size);
    }
    return ret;
}
