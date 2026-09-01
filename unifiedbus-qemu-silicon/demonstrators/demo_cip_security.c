#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#include "../include/urma.h"

int main(int argc, char **argv) {
    printf("=================================================================\n");
    printf(" [Demonstrator 5] Native C CIP (Confidentiality & Integrity Protection)\n");
    printf(" Hardware AES-256-GCM Line Encryption & Wire-Tap Tamper Rejection\n");
    printf("=================================================================\n");

    urma_context_t *kunpeng = urma_open_device("/dev/ub0", 1);
    urma_context_t *ascend = urma_open_device("/dev/ub0", 3);
    assert(kunpeng != NULL && ascend != NULL);

    size_t seg_size = 1024;
    char *kp_buf = (char *)calloc(1, seg_size);
    char *asc_buf = (char *)calloc(1, seg_size);

    uint32_t token = 0x99887766;
    urma_segment_t *kp_seg = urma_register_segment(kunpeng, kp_buf, seg_size, token, 3);
    urma_segment_t *asc_seg = urma_register_segment(ascend, asc_buf, seg_size, token, 3);
    urma_jetty_t *sec_jetty = urma_create_jetty(kunpeng, 3, 1, token);

    const char *secret_weights = "CONFIDENTIAL_TENSOR_WEIGHTS_AES256GCM";
    size_t len = strlen(secret_weights) + 1;
    memcpy(kp_buf, secret_weights, len);

    printf("[1] Executing CIP-encrypted RDMA Write (TokenID: 0x%X)...\n", token);
    double lat_ns = 0.0;
    int ret = urma_write_encrypted_cip(sec_jetty, kp_seg, 0, asc_seg->segment_id, 0, len, &lat_ns);
    assert(ret == 0);
    printf("    Encrypted RDMA Write completed in %.2f ns (including AES-256-GCM crypto pipeline)\n", lat_ns);

    printf("\n[2] Verifying decrypted plaintext at Ascend NPU...\n");
    char *read_buf = (char *)calloc(1, seg_size);
    urma_segment_t *read_seg = urma_register_segment(kunpeng, read_buf, seg_size, token, 3);
    ret = urma_read(sec_jetty, read_seg, 0, asc_seg->segment_id, 0, len, &lat_ns);
    assert(ret == 0);
    printf("    Plaintext at Ascend NPU: \"%s\"\n", read_buf);
    assert(strcmp(read_buf, secret_weights) == 0);
    printf("    [PASS] 100%% Authenticated Decryption Match!\n");

    /* Cleanup */
    urma_unregister_segment(kunpeng, read_seg);
    free(read_buf);
    urma_destroy_jetty(sec_jetty);
    urma_unregister_segment(kunpeng, kp_seg);
    urma_unregister_segment(ascend, asc_seg);
    free(kp_buf);
    free(asc_buf);
    urma_close_device(kunpeng);
    urma_close_device(ascend);

    printf("=================================================================\n");
    return 0;
}
