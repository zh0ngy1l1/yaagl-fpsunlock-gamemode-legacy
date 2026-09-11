/* Additional review cases operate only on the fixture's local byte array. */
static unsigned review_matrix_cases, review_query_cases, review_first_failure_cases;
static void review_tests(void)
{
    const DWORD protection[] = { 1, 2, 4, 8, 0x10, 0x20, 0x40, 0x80 };
    for (size_t allocation = 0; allocation < 8; allocation++) {
        for (size_t current = 0; current < 8; current++) {
            reset(protection[allocation], protection[current], 60);
            /* Invoke the helper alone: this asserts classification, not that
             * writes to read-only/noaccess pages succeed on an actual host. */
            corrected_toggle(PROCESS, (void *)(uintptr_t)FIELD_ADDRESS, 4);
            probe();
            int executable = current >= 4;
            check(m.query_calls == 1 && m.protect_calls == (executable ? 2 : 0),
                  "full allocation/current matrix follows current executable class");
            check(m.current_protect == protection[current], "matrix restores or retains current protection");
            if (executable) check(m.requested[0] == protection[current - 4] &&
                                  m.protection_status[0] == 0 && m.protection_status[1] == 0,
                                  "base executable protection maps to valid corresponding nonexec access");
            review_matrix_cases++;
        }
    }
    reset(0x80, 8, 60);
    m.query_status = STATUS_ACCESS_DENIED;
    struct outcome first = write_then_helper(1, 160, 0, 4);
    check(first.queries == 1 && first.protects == 0, "failed helper query makes no protection call");
    m.query_status = 0;
    struct outcome second = write_then_helper(1, 160, 0, 4);
    check(second.queries == 2 && second.protects == 0, "next invocation refreshes after query failure");
    review_query_cases++;

    reset(0x80, 8, 60);
    first = write_then_helper(1, 160, 0, 4);
    m.info.Protect = m.current_protect = 0x20;
    second = write_then_helper(1, 160, 0, 4);
    check(first.protects == 0 && second.queries == 2 && second.protects == 2 && second.final_protect == 0x20,
          "second helper query sees current page transition from data to executable");
    review_query_cases++;

    reset(0x80, 0x20, 60);
    first = write_then_helper(1, 160, 0, 4);
    m.info.Protect = m.current_protect = 4;
    second = write_then_helper(1, 160, 0, 4);
    check(first.protects == 2 && second.queries == 2 && second.protects == 2 && second.final_protect == 4,
          "second helper query sees executable-to-data transition and adds no stale toggle");
    review_query_cases++;

    const DWORD failure_allocations[] = {0x80, 4};
    for (size_t index = 0; index < 2; index++) {
        reset(failure_allocations[index], 0x20, 60);
        m.first_protect_status = STATUS_ACCESS_DENIED;
        first = write_then_helper(1, 160, 0, 4);
        check(first.status == 0 && first.protects == 2 && first.final_protect == PAGE_NOACCESS &&
              first.fps_faults == 1 && first.neighbor_faults == 1,
              "ignored first-protect failure can use returned noaccess as restoration protection");
        /* Pinned Wine NtProtectVirtualMemory sets old_prot=PAGE_NOACCESS for
         * a queued remote APC's target-side failure. Its separate queue-failure
         * branch leaves old_prot untouched, checked by static analysis only. */
        review_first_failure_cases++;
    }
}
