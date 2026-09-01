#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "ubus_driver.h"

#define MAX_HANDLES 64

static ub_silicon_fabric_t *g_fabric = NULL;
static ubus_dev_state_t g_devs[MAX_HANDLES];
static uint32_t g_next_seg_id = 1;
static uint32_t g_next_jetty_id = 1;

int ubus_driver_init(ub_silicon_fabric_t *fabric) {
    g_fabric = fabric;
    memset(g_devs, 0, sizeof(g_devs));
    return 0;
}

void ubus_driver_cleanup(void) {
    g_fabric = NULL;
}

int ubus_dev_open(uint16_t node_id) {
    if (!g_fabric) {
        g_fabric = ub_silicon_fabric_init(800.0, 15.0);
    }
    if (node_id >= MAX_HANDLES) return -1;
    if (g_devs[node_id].is_open) return node_id;

    g_devs[node_id].node_id = node_id;
    g_devs[node_id].fabric = g_fabric;
    g_devs[node_id].is_open = 1;

    ub_silicon_register_node(g_fabric, node_id, "KUNPENG_OR_ASCEND");
    return node_id;
}

int ubus_dev_close(int handle) {
    if (handle < 0 || handle >= MAX_HANDLES || !g_devs[handle].is_open) return -1;
    ub_silicon_unregister_node(g_fabric, (uint16_t)handle);
    g_devs[handle].is_open = 0;
    return 0;
}

int ubus_dev_ioctl(int handle, unsigned int cmd, void *arg) {
    if (handle < 0 || handle >= MAX_HANDLES || !g_devs[handle].is_open || !arg) return -1;
    uint16_t node_id = g_devs[handle].node_id;

    switch (cmd) {
        case UB_IOCTL_GET_DEV_INFO: {
            struct ub_ioctl_dev_info *info = (struct ub_ioctl_dev_info *)arg;
            info->node_id = node_id;
            info->vendor_id = UB_PCI_VENDOR_ID;
            info->device_id = UB_PCI_DEVICE_ID;
            info->hw_version = UB_HW_VERSION;
            info->link_status = g_fabric->nodes[node_id].link_up ? 1 : 0;
            info->link_speed_gbps = (uint32_t)g_fabric->link_bw_gbps;
            info->bar0_size = 64 * 1024;
            info->bar1_size = 1024 * 1024;
            info->bar2_size = 256 * 1024;
            info->bar3_size = NODE_MEM_SIZE;
            return 0;
        }

        case UB_IOCTL_REG_SEG: {
            struct ub_ioctl_reg_seg *reg = (struct ub_ioctl_reg_seg *)arg;
            uint32_t seg_id = g_next_seg_id++;
            uint64_t offset = (seg_id - 1) * (1024 * 1024); /* 1MB stride in BAR3 aperture */
            
            ub_silicon_register_segment(g_fabric, node_id, seg_id, offset, reg->size, reg->token_id, reg->permissions);
            reg->segment_id = seg_id;
            return 0;
        }

        case UB_IOCTL_CREATE_JETTY: {
            struct ub_ioctl_create_jetty *cj = (struct ub_ioctl_create_jetty *)arg;
            uint32_t j_id = g_next_jetty_id++;
            ub_silicon_create_jetty(g_fabric, node_id, j_id, cj->remote_node, cj->remote_jetty_id, cj->token_id);
            cj->jetty_id = j_id;
            return 0;
        }

        case UB_IOCTL_SUBMIT_WR: {
            struct ub_ioctl_submit_wr *wr = (struct ub_ioctl_submit_wr *)arg;
            ub_hw_descriptor_t desc;
            memset(&desc, 0, sizeof(desc));
            desc.opcode = wr->opcode;
            desc.flags = wr->flags;
            desc.src_node = node_id;
            desc.dst_node = g_fabric->nodes[node_id].jetties[wr->jetty_id].remote_node;
            desc.token_id = g_fabric->nodes[node_id].jetties[wr->jetty_id].token_id;
            desc.remote_seg_id = wr->remote_seg_id;
            desc.local_seg_id = wr->local_seg_id;
            desc.dst_offset = wr->remote_offset;
            desc.src_offset = wr->local_offset;
            desc.length = wr->length;

            if (wr->opcode == 0x67) { /* CAS */
                desc.src_offset = wr->compare_val;
                desc.dst_offset = wr->swap_val;
            } else if (wr->opcode == 0x68) { /* Add */
                desc.dst_offset = wr->swap_val;
            }

            uint8_t *user_ptr = (uint8_t*)wr->local_offset; /* Virtual buffer address */
            char err[128];
            int ret = ub_silicon_process_wr(g_fabric, node_id, &desc, user_ptr, user_ptr, &wr->sim_latency_ns, err, sizeof(err));
            if (ret != 0) {
                fprintf(stderr, "[Kernel Driver Error] WR failed: %s (code %d)\n", err, ret);
                return ret;
            }
            if (wr->opcode == 0x67 || wr->opcode == 0x68) {
                wr->orig_val = desc.status;
            }
            return 0;
        }

        case UB_IOCTL_QUERY_STATS: {
            struct ub_ioctl_stats *st = (struct ub_ioctl_stats *)arg;
            ub_silicon_node_t *n = &g_fabric->nodes[node_id];
            st->tx_flits = n->tx_flits;
            st->rx_flits = n->rx_flits;
            st->tx_bytes = n->tx_bytes;
            st->rx_bytes = n->rx_bytes;
            st->crc_errors = n->crc_errors;
            st->cip_tamper_errors = n->cip_tamper_errors;
            st->cip_replay_errors = n->cip_replay_errors;
            return 0;
        }

        default:
            return -EINVAL;
    }
}
