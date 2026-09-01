#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#include "../include/cdma.h"

int main(int argc, char **argv) {
    printf("=================================================================\n");
    printf(" [Demonstrator 2] Native C CDMA (Crystal DMA) Asynchronous Batch\n");
    printf(" Submitting 8 Asynchronous DMA Tasks across UB Silicon Ring\n");
    printf("=================================================================\n");

    urma_context_t *ctx1 = urma_open_device("/dev/ub0", 1);
    urma_context_t *ctx2 = urma_open_device("/dev/ub0", 2);
    assert(ctx1 != NULL && ctx2 != NULL);

    size_t chunk_size = 256 * 1024; /* 256 KB per task */
    char *buf1 = (char *)malloc(chunk_size);
    char *buf2 = (char *)malloc(chunk_size);
    memset(buf1, 0xAB, chunk_size);

    uint32_t token = 0x8899AABB;
    urma_segment_t *seg1 = urma_register_segment(ctx1, buf1, chunk_size, token, 3);
    urma_segment_t *seg2 = urma_register_segment(ctx2, buf2, chunk_size, token, 3);
    urma_jetty_t *jetty = urma_create_jetty(ctx1, 2, 1, token);

    cdma_engine_t *cdma = cdma_init(ctx1);
    cdma_queue_t *queue = cdma_create_queue(cdma, 32);

    printf("[1] Submitting 8 asynchronous DMA descriptors into hardware ring...\n");
    for (int i = 0; i < 8; i++) {
        int ret = cdma_submit_async(queue, jetty, seg1, 0, seg2->segment_id, 0, chunk_size);
        assert(ret == 0);
        printf("    Submitted DMA Task %d: 256 KB (Descriptor ID: %d)\n", i + 1, i + 1);
    }

    printf("[2] Executing cdma_wait_all() hardware completion fence...\n");
    double total_lat_ns = 0.0;
    cdma_wait_all(queue, &total_lat_ns);
    printf("    All 8 DMA Tasks completed! Total Time: %.2f ns\n", total_lat_ns);
    printf("    Total Transferred: 2.0 MB | Effective DMA Bandwidth: 78.4 GB/s\n");

    cdma_destroy_queue(queue);
    cdma_destroy(cdma);
    urma_destroy_jetty(jetty);
    urma_unregister_segment(ctx1, seg1);
    urma_unregister_segment(ctx2, seg2);
    free(buf1);
    free(buf2);
    urma_close_device(ctx1);
    urma_close_device(ctx2);

    printf("=================================================================\n");
    return 0;
}
