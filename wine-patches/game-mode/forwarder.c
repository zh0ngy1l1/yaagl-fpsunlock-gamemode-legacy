/* Preserve Wine's established loader path, but exec its actual bundled path.
 * No shell, environment changes, forks, or modification of inherited descriptors. */
#include <mach-o/dyld.h>
#include <errno.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
int main(int argc, char **argv)
{
    char raw[PATH_MAX], *path, *slash, *target;
    uint32_t size = sizeof(raw);
    (void)argc;
    if (_NSGetExecutablePath(raw, &size) || !(path = realpath(raw, NULL))) {
        fputs("wine: cannot locate bundled loader forwarder\n", stderr);
        return 127;
    }
    slash = strrchr(path, '/');
    if (!slash) { free(path); return 127; }
    *slash = 0;
    if (asprintf(&target, "%s/WineGame.app/Contents/MacOS/wine", path) < 0) {
        free(path); return 127;
    }
    free(path);
    argv[0] = target;
    execv(target, argv);
    fprintf(stderr, "wine: cannot exec %s: %s\n", target, strerror(errno));
    free(target);
    return 127;
}
