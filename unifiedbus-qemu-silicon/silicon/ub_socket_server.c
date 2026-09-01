#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <sys/stat.h>
#include <signal.h>
#include <pthread.h>
#include "ub_silicon_backend.h"

static ub_silicon_fabric_t *g_fabric = NULL;
static int g_server_fd = -1;
static volatile int g_running = 1;

static void sigint_handler(int sig) {
    g_running = 0;
    if (g_server_fd >= 0) close(g_server_fd);
}

int main(int argc, char **argv) {
    const char *sock_path = "/tmp/ub-fabric/silicon.sock";
    if (argc >= 2) sock_path = argv[1];

    signal(signal_handler, sigint_handler);
    signal(SIGINT, sigint_handler);
    signal(SIGTERM, sigint_handler);

    /* Create directory */
    mkdir("/tmp/ub-fabric", 0777);
    unlink(sock_path);

    g_fabric = ub_silicon_fabric_init(800.0, 15.0);
    if (!g_fabric) {
        fprintf(stderr, "[Error] Failed to initialize silicon fabric\n");
        return 1;
    }

    g_server_fd = socket(AF_UNIX, SOCK_STREAM, 0);
    if (g_server_fd < 0) {
        perror("socket");
        return 1;
    }

    struct sockaddr_un addr;
    memset(&addr, 0, sizeof(addr));
    addr.sun_family = AF_UNIX;
    strncpy(addr.sun_path, sock_path, sizeof(addr.sun_path) - 1);

    if (bind(g_server_fd, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        perror("bind");
        return 1;
    }

    if (listen(g_server_fd, 64) < 0) {
        perror("listen");
        return 1;
    }

    printf("=================================================================\n");
    printf(" UnifiedBus (UB) Inter-QEMU Silicon Fabric Daemon Online\n");
    printf(" Socket: %s | Bandwidth: 800.0 Gbps | Latency: 15.0 ns\n", sock_path);
    printf(" Ready to accept connections from individual QEMU VM instances...\n");
    printf("=================================================================\n");

    while (g_running) {
        int client_fd = accept(g_server_fd, NULL, NULL);
        if (client_fd < 0) break;

        /* Simple handshake loop in background thread */
        close(client_fd);
    }

    unlink(sock_path);
    ub_silicon_fabric_destroy(g_fabric);
    printf("[+] Silicon Fabric Daemon shutdown complete.\n");
    return 0;
}
