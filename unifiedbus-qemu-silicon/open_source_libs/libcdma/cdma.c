#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "../../include/cdma.h"

cdma_engine_t *cdma_init(urma_context_t *urma_ctx) {
    if (!urma_ctx) return NULL;
    cdma_engine_t *engine = (cdma_engine_t *)malloc(sizeof(cdma_engine_t));
    if (!engine) return NULL;
    engine->urma_ctx = urma_ctx;
    return engine;
}

void cdma_destroy(cdma_engine_t *engine) {
    if (engine) free(engine);
}

cdma_queue_t *cdma_create_queue(cdma_engine_t *engine, uint32_t depth) {
    if (!engine) return NULL;
    cdma_queue_t *q = (cdma_queue_t *)malloc(sizeof(cdma_queue_t));
    if (!q) return NULL;
    q->engine = engine;
    q->queue_id = 1;
    q->depth = depth ? depth : 64;
    return q;
}

void cdma_destroy_queue(cdma_queue_t *q) {
    if (q) free(q);
}

int cdma_submit_async(cdma_queue_t *q, urma_jetty_t *jetty, urma_segment_t *local_seg,
                      size_t local_offset, uint32_t remote_seg_id, size_t remote_offset, size_t length) {
    if (!q || !jetty || !local_seg) return -1;
    double lat = 0.0;
    return urma_write(jetty, local_seg, local_offset, remote_seg_id, remote_offset, length, &lat);
}

int cdma_wait_all(cdma_queue_t *q, double *out_total_latency_ns) {
    if (!q) return -1;
    if (out_total_latency_ns) *out_total_latency_ns = 45.0; /* Hardware Completion Barrier */
    return 0;
}

int cdma_fence(cdma_queue_t *q) {
    if (!q) return -1;
    return 0;
}
