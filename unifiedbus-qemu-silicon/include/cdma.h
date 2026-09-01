#ifndef CDMA_H
#define CDMA_H

#include <stdint.h>
#include <stddef.h>
#include "urma.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct cdma_engine cdma_engine_t;
typedef struct cdma_queue  cdma_queue_t;

struct cdma_engine {
    urma_context_t *urma_ctx;
};

struct cdma_queue {
    cdma_engine_t *engine;
    uint32_t queue_id;
    uint32_t depth;
};

/* Official CDMA C Library Functions */
cdma_engine_t *cdma_init(urma_context_t *urma_ctx);
void cdma_destroy(cdma_engine_t *engine);

cdma_queue_t *cdma_create_queue(cdma_engine_t *engine, uint32_t depth);
void cdma_destroy_queue(cdma_queue_t *q);

int cdma_submit_async(cdma_queue_t *q, urma_jetty_t *jetty, urma_segment_t *local_seg,
                      size_t local_offset, uint32_t remote_seg_id, size_t remote_offset, size_t length);

int cdma_wait_all(cdma_queue_t *q, double *out_total_latency_ns);
int cdma_fence(cdma_queue_t *q);

#ifdef __cplusplus
}
#endif

#endif /* CDMA_H */
