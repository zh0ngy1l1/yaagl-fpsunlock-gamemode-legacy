/* Native host fixture: no Wine library, process attachment or game execution.
 * The helper bodies included below are extracted byte-for-byte as C source
 * from the matching downstream patch. Only the corrected body substitutes
 * info.Protect for both info.AllocationProtect references. All native APIs
 * below are deterministic mocks, not imports or process-memory operations.
 */
#include <inttypes.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef void *HANDLE;
typedef uint32_t DWORD;
typedef uint32_t NTSTATUS;
typedef size_t SIZE_T;
typedef struct {
    void *BaseAddress;
    void *AllocationBase;
    DWORD AllocationProtect;
    uint16_t PartitionId;
    SIZE_T RegionSize;
    DWORD State;
    DWORD Protect;
    DWORD Type;
} MEMORY_BASIC_INFORMATION;
_Static_assert(sizeof(MEMORY_BASIC_INFORMATION) == 48, "matching x64 MBI width");
_Static_assert(offsetof(MEMORY_BASIC_INFORMATION, AllocationProtect) == 16, "old operand");
_Static_assert(offsetof(MEMORY_BASIC_INFORMATION, Protect) == 36, "corrected operand");
enum { MemoryBasicInformation = 0, PAGE_NOACCESS = 1 };
#define FIELD_ADDRESS UINT64_C(0x1452b4244)
#define NEIGHBOR_ADDRESS UINT64_C(0x1452b4ad8)
#define PAGE_ADDRESS UINT64_C(0x1452b4000)
#define PROCESS ((HANDLE)(uintptr_t)0x99)
#define STATUS_ACCESS_DENIED UINT32_C(0xc0000022)
#define STATUS_PARTIAL_COPY UINT32_C(0x8000000d)

struct mock {
    MEMORY_BASIC_INFORMATION info;
    uint8_t page[4096], initial_neighbor[8];
    NTSTATUS query_status, restore_status;
    int translated, pending_probe, query_calls, protect_calls;
    int fps_probe_faults, neighbor_probe_faults, query_wrong_process;
    DWORD requested[2];
    uintptr_t protected_address[2];
    size_t protected_size[2];
    DWORD current_protect;
};
static struct mock m;
static unsigned checks, target_cases, low_payload_cases, protection_cases, status_cases;
static void check(int ok, const char *message)
{
    checks++;
    if (!ok) { fprintf(stderr, "FAIL: %s\n", message); exit(1); }
}
static int is_apple_silicon(void) { return m.translated; }
static int readable(uintptr_t address, size_t width)
{
    if (address < PAGE_ADDRESS || width > sizeof(m.page) ||
        address - PAGE_ADDRESS > sizeof(m.page) - width) return 0;
    if (m.current_protect & 0x100) return 0; /* guard */
    DWORD base = m.current_protect & 0xff;
    return base == 2 || base == 4 || base == 8 || base == 0x20 ||
           base == 0x40 || base == 0x80;
}
static void probe(void)
{
    if (!m.pending_probe) return;
    m.pending_probe = 0;
    m.fps_probe_faults += !readable(FIELD_ADDRESS, 4);
    m.neighbor_probe_faults += !readable(NEIGHBOR_ADDRESS, 8);
}
static NTSTATUS NtQueryVirtualMemory(HANDLE process, const void *address, int kind,
                                    MEMORY_BASIC_INFORMATION *info, SIZE_T length, SIZE_T *ret)
{
    m.query_calls++;
    m.query_wrong_process += process != PROCESS;
    check((uintptr_t)address == FIELD_ADDRESS && kind == MemoryBasicInformation &&
          length == sizeof(*info), "helper queries bound target field and full MBI");
    if (m.query_status) return m.query_status;
    *info = m.info;
    *ret = sizeof(*info);
    m.pending_probe = 1; /* constructed game read after query, during first toggle if any */
    return 0;
}
static NTSTATUS NtProtectVirtualMemory(HANDLE process, void **address, SIZE_T *size,
                                      DWORD requested, DWORD *original)
{
    check(process == PROCESS, "helper protects the target process");
    int index = m.protect_calls++;
    check(index < 2, "at most original toggle/restore pair");
    m.requested[index] = requested;
    m.protected_address[index] = (uintptr_t)*address;
    m.protected_size[index] = *size;
    *original = m.current_protect;
    if (index == 1 && m.restore_status) return m.restore_status;
    m.current_protect = requested;
    /* Model the page rounding in NtProtectVirtualMemory, not a real protection call. */
    uintptr_t start = (uintptr_t)*address;
    uintptr_t end = (start + *size + 4095) & ~(uintptr_t)4095;
    *address = (void *)(start & ~(uintptr_t)4095);
    *size = end - (uintptr_t)*address;
    probe();
    return 0;
}

#define toggle_executable_pages_for_rosetta legacy_toggle
#include "helper-legacy.inc"
#undef toggle_executable_pages_for_rosetta
#define toggle_executable_pages_for_rosetta corrected_toggle
#include "helper-corrected.inc"
#undef toggle_executable_pages_for_rosetta

struct outcome {
    NTSTATUS status;
    size_t bytes;
    int32_t value;
    int neighbor_unchanged, queries, protects, fps_faults, neighbor_faults;
    DWORD final_protect, first_request;
};

static void reset(DWORD allocation_protect, DWORD current_protect, int32_t before)
{
    memset(&m, 0, sizeof(m));
    m.info.BaseAddress = (void *)(uintptr_t)PAGE_ADDRESS;
    m.info.AllocationBase = (void *)(uintptr_t)UINT64_C(0x140000000);
    m.info.AllocationProtect = allocation_protect;
    m.info.RegionSize = UINT64_C(0x980000);
    m.info.State = 0x1000;
    m.info.Protect = current_protect;
    m.info.Type = 0x1000000;
    m.current_protect = current_protect;
    m.translated = 1;
    memcpy(m.page + (FIELD_ADDRESS - PAGE_ADDRESS), &before, 4);
    const uint32_t infinity[2] = { 0x7f800000, 0x7f800000 };
    memcpy(m.page + (NEIGHBOR_ADDRESS - PAGE_ADDRESS), infinity, 8);
    memcpy(m.initial_neighbor, infinity, 8);
}

/* Only call order/status propagation around the extracted helper is modeled:
 * installed NtWriteVirtualMemory invokes it after the server reply even on an
 * unsuccessful server status and returns that original status and byte count.
 * This fixture does not implement the Mach write, server APC or Rosetta runtime.
 */
static struct outcome write_then_helper(int corrected, int32_t target,
                                       NTSTATUS server_status, size_t bytes_written)
{
    check(bytes_written <= 4, "fixture only writes the requested four-byte scalar");
    memcpy(m.page + (FIELD_ADDRESS - PAGE_ADDRESS), &target, bytes_written);
    if (corrected) corrected_toggle(PROCESS, (void *)(uintptr_t)FIELD_ADDRESS, bytes_written);
    else legacy_toggle(PROCESS, (void *)(uintptr_t)FIELD_ADDRESS, bytes_written);
    probe(); /* no toggle means the scheduled read sees the original accessible page */
    struct outcome result = { .status = server_status, .bytes = bytes_written,
        .neighbor_unchanged = !memcmp(m.initial_neighbor, m.page + (NEIGHBOR_ADDRESS - PAGE_ADDRESS), 8),
        .queries = m.query_calls, .protects = m.protect_calls,
        .fps_faults = m.fps_probe_faults, .neighbor_faults = m.neighbor_probe_faults,
        .final_protect = m.current_protect, .first_request = m.requested[0] };
    memcpy(&result.value, m.page + (FIELD_ADDRESS - PAGE_ADDRESS), 4);
    check(!m.query_wrong_process, "query uses supplied remote process, never current process");
    return result;
}

static void self_test(void)
{
    for (int target = 61; target <= 360; target++) {
        reset(0x80, 8, 60);
        struct outcome old = write_then_helper(0, target, 0, 4);
        check(old.status == 0 && old.bytes == 4 && old.value == target,
              "legacy reports full exact target despite concurrent read faults");
        check(old.protects == 2 && old.first_request == PAGE_NOACCESS && old.final_protect == 8,
              "legacy allocation classification creates and restores noaccess pulse");
        check(old.fps_faults == 1 && old.neighbor_faults == 1 && old.neighbor_unchanged,
              "legacy pulse faults both fields without overlapping neighbor payload");
        reset(0x80, 8, 60);
        struct outcome now = write_then_helper(1, target, 0, 4);
        check(now.status == 0 && now.bytes == 4 && now.value == target,
              "corrected exact target written with original status/length");
        check(now.protects == 0 && now.final_protect == 8 &&
              !now.fps_faults && !now.neighbor_faults && now.neighbor_unchanged,
              "corrected nonexec data remains accessible throughout modeled interval");
        /* Game reset is a game-local store; same update primitive must work again. */
        int32_t reset_value = 60;
        memcpy(m.page + (FIELD_ADDRESS - PAGE_ADDRESS), &reset_value, 4);
        now = write_then_helper(1, target, 0, 4);
        check(now.value == target && now.protects == 0 && !now.fps_faults && !now.neighbor_faults,
              "game reset reapplication retains exact target and accessibility");
        reset(0x80, 8, -1);
        now = write_then_helper(1, target, 0, 4);
        check(now.value == target && !now.protects && !now.fps_faults && !now.neighbor_faults,
              "release early update from initializer sentinel has no data protection pulse");
        target_cases++;
    }
    /* Generic native data path remains independent of numeric value. These
     * are payload checks, not permission to launch a companion for <=60. */
    for (int target = 0; target <= 60; target++) {
        reset(0x80, 8, -1);
        struct outcome result = write_then_helper(1, target, 0, 4);
        check(result.value == target && !result.protects && !result.fps_faults && !result.neighbor_faults,
              "zero and <=60 scalar payload semantics are unchanged by page classification");
        low_payload_cases++;
    }
    const DWORD executable[] = { 0x10, 0x20, 0x40, 0x80 };
    const DWORD modifiers[] = { 0, 0x100, 0x200, 0x400, 0x40000000 };
    for (size_t p = 0; p < sizeof(executable)/sizeof(*executable); p++)
        for (size_t f = 0; f < sizeof(modifiers)/sizeof(*modifiers); f++) {
            DWORD prot = executable[p] | modifiers[f];
            reset(prot, prot, 60); struct outcome old = write_then_helper(0, 160, 0, 4);
            reset(prot, prot, 60); struct outcome now = write_then_helper(1, 160, 0, 4);
            check(old.protects == now.protects && old.first_request == now.first_request &&
                  old.final_protect == now.final_protect && now.final_protect == prot,
                  "same executable current/allocation protections retain exact original behavior");
            protection_cases++;
        }
    /* Differing executable current protection: current region, not allocation metadata,
     * supplies both the predicate and preserved non-executable modifier bits. */
    reset(0x80, 0x240, 60); struct outcome mixed = write_then_helper(1, 160, 0, 4);
    check(mixed.protects == 2 && mixed.first_request == 0x200 && mixed.final_protect == 0x240,
          "corrected actual executable page preserves its own modifier bits");
    reset(8, 0x40, 60); mixed = write_then_helper(1, 160, 0, 4);
    check(mixed.protects == 2 && mixed.first_request == PAGE_NOACCESS && mixed.final_protect == 0x40,
          "actual executable page still invalidates when its allocation was nonexecutable");
    reset(4, 0x20, 60); struct outcome opposite_old = write_then_helper(0, 160, 0, 4);
    reset(4, 0x20, 60); struct outcome opposite_now = write_then_helper(1, 160, 0, 4);
    check(opposite_old.protects == 0 && opposite_now.protects == 2 &&
          opposite_now.first_request == PAGE_NOACCESS && opposite_now.final_protect == 0x20,
          "allocation RW/current executable-read mismatch now receives intended invalidation");
    for (DWORD prot = 1; prot <= 8; prot <<= 1)
        for (size_t f = 0; f < sizeof(modifiers)/sizeof(*modifiers); f++) {
            reset(0x80, prot | modifiers[f], 60);
            struct outcome now = write_then_helper(1, 160, 0, 4);
            check(now.protects == 0 && now.final_protect == (prot | modifiers[f]),
                  "nonexec current pages never receive cache invalidation, modifiers retained");
            protection_cases++;
        }
    for (int corrected = 0; corrected <= 1; corrected++) {
        reset(0x80, 8, 60); m.query_status = STATUS_ACCESS_DENIED;
        struct outcome result = write_then_helper(corrected, 160, 0, 4);
        check(result.status == 0 && result.bytes == 4 && result.protects == 0,
              "failed postwrite query retains server success and does not toggle"); status_cases++;
        reset(0x80, 8, 60); m.translated = 0;
        result = write_then_helper(corrected, 160, 0, 4);
        check(!result.queries && !result.protects && result.status == 0,
              "nontranslated path unchanged and never queries or toggles"); status_cases++;
        reset(0x80, 8, 60); m.query_status = STATUS_ACCESS_DENIED;
        result = write_then_helper(corrected, 160, STATUS_ACCESS_DENIED, 0);
        check(result.status == STATUS_ACCESS_DENIED && result.bytes == 0 && result.value == 60 && !result.protects,
              "server failure/zero count propagate independently of failed helper query"); status_cases++;
        reset(0x80, 8, 60);
        result = write_then_helper(corrected, 160, STATUS_PARTIAL_COPY, 2);
        check(result.status == STATUS_PARTIAL_COPY && result.bytes == 2,
              "partial server result preserved rather than relabeled success"); status_cases++;
    }
    reset(0x80, 8, 60); m.restore_status = STATUS_ACCESS_DENIED;
    struct outcome result = write_then_helper(1, 160, 0, 4);
    check(!result.protects && result.final_protect == 8,
          "data correction removes exposure to both protection calls and restoration errors");
    reset(0x80, 0x80, 60); m.restore_status = STATUS_ACCESS_DENIED;
    result = write_then_helper(1, 160, 0, 4);
    check(result.status == 0 && result.final_protect == PAGE_NOACCESS,
          "residual executable-page ignored restoration error remains explicitly demonstrated");
    reset(0x80, 8, 60);
    result = write_then_helper(1, 160, STATUS_ACCESS_DENIED, 0);
    check(result.status == STATUS_ACCESS_DENIED && result.bytes == 0 && result.value == 60 && !result.protects,
          "corrected data path does not add a toggle even when failed server write still triggers helper");
    reset(0x80, 8, 0x12345678);
    result = write_then_helper(1, 360, STATUS_PARTIAL_COPY, 2);
    check(result.status == STATUS_PARTIAL_COPY && result.bytes == 2 && result.value == 0x12340168 && !result.protects,
          "partial byte transfer is modeled faithfully and retains partial status");
    printf("{\"checks\":%u,\"distinct_targets\":%u,\"zero_through_60_payload_cases\":%u,\"protection_cases\":%u,\"status_cases\":%u,"
           "\"source_helper_executed\":true,\"native_interfaces_mocked\":true,\"wine_executed\":false,"
           "\"game_executed\":false,\"historical_interleaving_recovered\":false}\n",
           checks, target_cases, low_payload_cases, protection_cases, status_cases);
}

static int batch(void)
{
    char line[256];
    while (fgets(line, sizeof(line), stdin)) {
        int corrected, target, before, translated;
        unsigned allocation, protect, server_status, query_status;
        size_t bytes;
        if (sscanf(line, "%d %d %d %x %x %x %zu %x %d", &corrected, &target, &before,
                   &allocation, &protect, &server_status, &bytes, &query_status, &translated) != 9) return 2;
        reset(allocation, protect, before); m.query_status = query_status; m.translated = translated;
        struct outcome r = write_then_helper(corrected, target, server_status, bytes);
        printf("{\"corrected\":%d,\"target\":%d,\"value\":%d,\"status\":%u,\"bytes\":%zu,"
               "\"protect_calls\":%d,\"first_protect\":%u,\"final_protect\":%u,"
               "\"fps_probe_faults\":%d,\"neighbor_probe_faults\":%d,\"neighbor_unchanged\":%d}\n",
               corrected, target, r.value, r.status, r.bytes, r.protects, r.first_request,
               r.final_protect, r.fps_faults, r.neighbor_faults, r.neighbor_unchanged);
    }
    return 0;
}
int main(int argc, char **argv)
{
    if (argc == 2 && !strcmp(argv[1], "--batch")) return batch();
    if (argc != 1) return 2;
    self_test(); return 0;
}
