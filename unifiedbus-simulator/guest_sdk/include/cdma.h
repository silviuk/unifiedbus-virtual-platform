#ifndef UNIFIEDBUS_CDMA_H
#define UNIFIEDBUS_CDMA_H

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct cdma_engine* cdma_engine_t;
typedef struct cdma_task*   cdma_task_t;

/* Initialize CDMA Engine */
cdma_engine_t cdma_init(uint16_t node_id, const char* socket_path);

/* Submit asynchronous DMA Write */
cdma_task_t cdma_submit_write(cdma_engine_t engine, uint16_t dst_node, uint32_t dst_seg_id, size_t dst_offset, const void* data, size_t len, uint32_t token_id);

/* Wait for task completion */
int cdma_task_wait(cdma_task_t task, uint32_t timeout_ms);

/* Free task resources */
void cdma_task_free(cdma_task_t task);

/* Destroy engine */
void cdma_close(cdma_engine_t engine);

#ifdef __cplusplus
}
#endif

#endif /* UNIFIEDBUS_CDMA_H */
