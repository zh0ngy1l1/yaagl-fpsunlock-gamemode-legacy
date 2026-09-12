/* Refuse packaging changes while any native executable from the engine runs. */
#include <libproc.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
int main(int argc, char **argv)
{
    char *root, path[PROC_PIDPATHINFO_MAXSIZE], resolved[PATH_MAX];
    int count, bytes, i, busy = 0;
    pid_t *pids;
    if (argc != 2 || !(root = realpath(argv[1], NULL))) return 2;
    bytes = proc_listpids(PROC_ALL_PIDS, 0, NULL, 0);
    if (bytes <= 0 || !(pids = calloc(1, bytes + 4096))) return 2;
    count = proc_listpids(PROC_ALL_PIDS, 0, pids, bytes + 4096) / sizeof(pid_t);
    if (count <= 0) return 2;
    for (i = 0; i < count; i++) {
        if (!pids[i] || pids[i] == getpid()) continue;
        if (proc_pidpath(pids[i], path, sizeof(path)) <= 0 || !realpath(path, resolved)) continue;
        if (!strncmp(root, resolved, strlen(root)) && resolved[strlen(root)] == '/') {
            fprintf(stderr, "Quit applications using this Wine engine before updating it (PID %d).\n", pids[i]);
            busy = 1;
        }
    }
    free(pids); free(root);
    return busy;
}
