#ifndef UNIFIEDBUS_OBMM_H
#define UNIFIEDBUS_OBMM_H

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct obmm_client* obmm_client_t;
typedef struct obmm_pool_handle* obmm_pool_t;

/* Initialize OBMM Client */
obmm_client_t obmm_init(uint16_t node_id, const char* socket_path);

/* Export local memory as globally accessible pool */
uint32_t obmm_export_pool(obmm_client_t client, size_t size_bytes, uint32_t token_id, const char* permissions);

/* Import remote memory pool */
obmm_pool_t obmm_import_pool(obmm_client_t client, uint32_t pool_id, uint32_t token_id);

/* Read/Write to borrowed memory pool */
int obmm_pool_write(obmm_pool_t pool, size_t offset, const void* src, size_t len);
int obmm_pool_read(obmm_pool_t pool, size_t offset, void* dst, size_t len);

/* Cleanup */
void obmm_pool_release(obmm_pool_t pool);
void obmm_close(obmm_client_t client);

#ifdef __cplusplus
}
#endif

#endif /* UNIFIEDBUS_OBMM_H */
