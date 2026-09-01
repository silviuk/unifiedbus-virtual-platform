#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#include "../include/urma.h"

int main(int argc, char **argv) {
    printf("=================================================================\n");
    printf(" [Demonstrator 1] Native C URMA P2P RDMA Transfer\n");
    printf(" Nodes: Kunpeng CPU (Node 1) <---> Ascend NPU (Node 3)\n");
    printf(" Link: 800 Gbps Low-Latency UnifiedBus Interconnect\n");
    printf("=================================================================\n");

    /* 1. Open device contexts */
    printf("[1] Initializing URMA hardware devices (/dev/ub0)...\n");
    urma_context_t *kunpeng = urma_open_device("/dev/ub0", 1);
    urma_context_t *ascend = urma_open_device("/dev/ub0", 3);
    assert(kunpeng != NULL && ascend != NULL);

    /* 2. Register DMA Memory Segments */
    size_t seg_size = 64 * 1024;
    char *kp_buf = (char *)calloc(1, seg_size);
    char *asc_buf = (char *)calloc(1, seg_size);

    uint32_t token = 0xCAFE1234;
    urma_segment_t *kp_seg = urma_register_segment(kunpeng, kp_buf, seg_size, token, 3);
    urma_segment_t *asc_seg = urma_register_segment(ascend, asc_buf, seg_size, token, 3);
    assert(kp_seg != NULL && asc_seg != NULL);
    printf("    Kunpeng registered Segment ID %u (Size: %lu KB, TokenID: 0x%X)\n", kp_seg->segment_id, seg_size/1024, token);
    printf("    Ascend registered Segment ID %u (Size: %lu KB, TokenID: 0x%X)\n", asc_seg->segment_id, seg_size/1024, token);

    /* 3. Create Jetty Endpoint */
    printf("[2] Establishing Hardware Jetty Endpoint connection...\n");
    urma_jetty_t *jetty = urma_create_jetty(kunpeng, 3, 1, token);
    assert(jetty != NULL);

    /* 4. Execute URMA Write */
    const char *payload = "Hello UnifiedBus Silicon Fabric from Kunpeng CPU 920!";
    size_t len = strlen(payload) + 1;
    memcpy(kp_buf, payload, len);

    printf("[3] Executing URMA RDMA Write (%lu bytes)...\n", len);
    double write_lat_ns = 0.0;
    int ret = urma_write(jetty, kp_seg, 0, asc_seg->segment_id, 0, len, &write_lat_ns);
    assert(ret == 0);
    printf("    URMA Write Confirmed! Hardware Latency: %.2f ns\n", write_lat_ns);

    /* 5. Execute URMA Read */
    printf("[4] Executing URMA RDMA Read back from Ascend NPU memory...\n");
    char *read_buf = (char *)calloc(1, seg_size);
    urma_segment_t *read_seg = urma_register_segment(kunpeng, read_buf, seg_size, token, 3);
    double read_lat_ns = 0.0;
    ret = urma_read(jetty, read_seg, 0, asc_seg->segment_id, 0, len, &read_lat_ns);
    assert(ret == 0);
    printf("    URMA Read Confirmed! Hardware Latency: %.2f ns\n", read_lat_ns);
    printf("    Read Data Content: \"%s\"\n", read_buf);

    assert(strcmp(read_buf, payload) == 0);
    printf("    [PASS] 100%% Data Integrity Verified across UB Silicon!\n");

    /* Cleanup */
    urma_unregister_segment(kunpeng, read_seg);
    free(read_buf);
    urma_destroy_jetty(jetty);
    urma_unregister_segment(kunpeng, kp_seg);
    urma_unregister_segment(ascend, asc_seg);
    free(kp_buf);
    free(asc_buf);
    urma_close_device(kunpeng);
    urma_close_device(ascend);

    printf("=================================================================\n");
    return 0;
}
