CC ?= gcc
CFLAGS ?= -O2 -Wall -fPIC -I./include -pthread
RPATH_FLAGS = -Wl,-rpath,'$$ORIGIN/..' -Wl,-rpath,'$$ORIGIN' -Wl,-rpath,.

# Targets
LIBS = libub_silicon.so liburma.so libcdma.so libobmm.so
BINARIES = ubctl/ubctl \
           demonstrators/demo_urma_p2p \
           demonstrators/demo_cdma_async \
           demonstrators/demo_obmm_memory_pool \
           demonstrators/demo_hccl_ring \
           demonstrators/demo_cip_security

all: $(LIBS) $(BINARIES)

# 1. Silicon Hardware & Kernel Driver Core
libub_silicon.so: silicon/ub_silicon_backend.c kernel/ubus_driver.c
	$(CC) $(CFLAGS) -shared -o $@ $^

# 2. Official Open-Source C Libraries
liburma.so: open_source_libs/liburma/urma.c libub_silicon.so
	$(CC) $(CFLAGS) -shared -o $@ $< -L. -lub_silicon $(RPATH_FLAGS)

libcdma.so: open_source_libs/libcdma/cdma.c liburma.so
	$(CC) $(CFLAGS) -shared -o $@ $< -L. -lurma -lub_silicon $(RPATH_FLAGS)

libobmm.so: open_source_libs/libobmm/obmm.c liburma.so
	$(CC) $(CFLAGS) -shared -o $@ $< -L. -lurma -lub_silicon $(RPATH_FLAGS)

# 3. Official ubctl CLI Tool
ubctl/ubctl: ubctl/ubctl.c libub_silicon.so
	$(CC) $(CFLAGS) -o $@ $< -L. -lub_silicon $(RPATH_FLAGS)

# 4. Demonstrator Binaries
demonstrators/demo_urma_p2p: demonstrators/demo_urma_p2p.c liburma.so libub_silicon.so
	$(CC) $(CFLAGS) -o $@ $< -L. -lurma -lub_silicon $(RPATH_FLAGS)

demonstrators/demo_cdma_async: demonstrators/demo_cdma_async.c libcdma.so liburma.so libub_silicon.so
	$(CC) $(CFLAGS) -o $@ $< -L. -lcdma -lurma -lub_silicon $(RPATH_FLAGS)

demonstrators/demo_obmm_memory_pool: demonstrators/demo_obmm_memory_pool.c libobmm.so liburma.so libub_silicon.so
	$(CC) $(CFLAGS) -o $@ $< -L. -lobmm -lurma -lub_silicon $(RPATH_FLAGS)

demonstrators/demo_hccl_ring: demonstrators/demo_hccl_ring.c liburma.so libub_silicon.so
	$(CC) $(CFLAGS) -o $@ $< -L. -lurma -lub_silicon $(RPATH_FLAGS)

demonstrators/demo_cip_security: demonstrators/demo_cip_security.c liburma.so libub_silicon.so
	$(CC) $(CFLAGS) -o $@ $< -L. -lurma -lub_silicon $(RPATH_FLAGS)

clean:
	rm -f $(LIBS) $(BINARIES) *.o

.PHONY: all clean
