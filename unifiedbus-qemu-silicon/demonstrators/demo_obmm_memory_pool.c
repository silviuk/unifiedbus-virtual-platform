#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#include "../include/obmm.h"

int main(int argc, char **argv) {
    printf("=================================================================\n");
    printf(" [Demonstrator 3] Native C OBMM (Open Block Memory Management)\n");
    printf(" 16 GB Disaggregated Memory Pool Loan over UnifiedBus Fabric\n");
    printf("=================================================================\n");

    /* Memory Exporter: Node 7 (Pooled Memory Appliance) */
    urma_context_t *exporter_ctx = urma_open_device("/dev/ub0", 7);
    obmm_client_t *exporter = obmm_init(exporter_ctx);

    size_t pool_size = 1024 * 1024; /* 1MB backing buffer in demo */
    char *pool_mem = (char *)calloc(1, pool_size);
    uint32_t token = 0xA1B2C3D4;

    printf("[1] Node 7 (Memory Appliance) exporting 16 GB memory pool (TokenID: 0x%X)...\n", token);
    uint32_t pool_id = obmm_export_pool(exporter, pool_mem, pool_size, token, 3);
    assert(pool_id > 0);
    printf("    Memory Pool 0x%X successfully registered on UB Global UMMU Directory.\n", pool_id);

    /* Memory Borrower 1: Node 1 (Kunpeng CPU) */
    printf("\n[2] Node 1 (Kunpeng CPU) importing remote memory pool 0x%X...\n", pool_id);
    urma_context_t *borrower1_ctx = urma_open_device("/dev/ub0", 1);
    obmm_client_t *borrower1 = obmm_init(borrower1_ctx);

    obmm_pool_handle_t *pool1 = obmm_import_pool(borrower1, 7, pool_id, pool_size, token);
    assert(pool1 != NULL);
    printf("    Node 1 mapped remote memory into local address space.\n");

    const char *data_str = "Global Shared Embedding Weights (Batch 001 - Transformer Model)";
    double write_lat_ns = 0.0;
    int ret = obmm_pool_write(pool1, 0, data_str, strlen(data_str) + 1, &write_lat_ns);
    assert(ret == 0);
    printf("    Node 1 wrote shared data into disaggregated pool (Latency: %.2f ns)\n", write_lat_ns);

    /* Memory Borrower 2: Node 3 (Ascend NPU) reads shared embeddings */
    printf("\n[3] Node 3 (Ascend NPU) accessing shared embeddings in pooled memory...\n");
    urma_context_t *borrower2_ctx = urma_open_device("/dev/ub0", 3);
    obmm_client_t *borrower2 = obmm_init(borrower2_ctx);

    obmm_pool_handle_t *pool2 = obmm_import_pool(borrower2, 7, pool_id, pool_size, token);
    assert(pool2 != NULL);

    char read_buf[256];
    double read_lat_ns = 0.0;
    ret = obmm_pool_read(pool2, 0, read_buf, strlen(data_str) + 1, &read_lat_ns);
    assert(ret == 0);
    printf("    Node 3 read shared data: \"%s\" (Latency: %.2f ns)\n", read_buf, read_lat_ns);
    assert(strcmp(read_buf, data_str) == 0);
    printf("    [PASS] Zero-copy pooled memory sharing verified!\n");

    /* Unauthorized Access Test: Node 4 with bad token */
    printf("\n[4] Security Isolation Test: Node 4 attempts access with wrong TokenID (0xBAD)...\n");
    urma_context_t *bad_ctx = urma_open_device("/dev/ub0", 4);
    obmm_client_t *bad_cli = obmm_init(bad_ctx);
    obmm_pool_handle_t *bad_pool = obmm_import_pool(bad_cli, 7, pool_id, pool_size, 0xBAD);
    
    char dummy_buf[64];
    ret = obmm_pool_read(bad_pool, 0, dummy_buf, 32, &read_lat_ns);
    if (ret != 0) {
        printf("    [DEFENSE ACTIVE] Unauthorized access blocked by UMMU TokenID check!\n");
    } else {
        printf("    [FAIL] Security check bypassed!\n");
    }

    /* Cleanup */
    obmm_release_pool(pool1);
    obmm_release_pool(pool2);
    obmm_release_pool(bad_pool);
    obmm_destroy(exporter);
    obmm_destroy(borrower1);
    obmm_destroy(borrower2);
    obmm_destroy(bad_cli);
    free(pool_mem);
    urma_close_device(exporter_ctx);
    urma_close_device(borrower1_ctx);
    urma_close_device(borrower2_ctx);
    urma_close_device(bad_ctx);

    printf("=================================================================\n");
    return 0;
}
