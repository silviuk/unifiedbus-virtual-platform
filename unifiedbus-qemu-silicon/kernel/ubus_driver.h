#ifndef UBUS_DRIVER_H
#define UBUS_DRIVER_H

#include <stdint.h>
#include <stddef.h>
#include "../include/ubus_hw.h"
#include "../include/ubus_ioctl.h"
#include "../silicon/ub_silicon_backend.h"

typedef struct {
    uint16_t node_id;
    ub_silicon_fabric_t *fabric;
    int is_open;
} ubus_dev_state_t;

/* Kernel Driver Interface */
int ubus_driver_init(ub_silicon_fabric_t *fabric);
void ubus_driver_cleanup(void);

int ubus_dev_open(uint16_t node_id);
int ubus_dev_close(int handle);
int ubus_dev_ioctl(int handle, unsigned int cmd, void *arg);

#endif /* UBUS_DRIVER_H */
