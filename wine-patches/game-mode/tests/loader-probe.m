#import <Foundation/Foundation.h>
#import <mach-o/dyld.h>
#import <unistd.h>
#import <stdlib.h>
void __wine_main(int argc, char **argv)
{
    @autoreleasepool {
        NSMutableArray *args = [NSMutableArray array];
        for (int i = 0; i < argc; i++) [args addObject:@(argv[i])];
        char path[4096]; uint32_t size = sizeof(path);
        _NSGetExecutablePath(path, &size);
        const char *fd = getenv("PROBE_FD");
        if (fd) write(atoi(fd), "inherited", 9);
        NSBundle *bundle = NSBundle.mainBundle;
        NSDictionary *data = @{
            @"pid": @(getpid()), @"args": args, @"executable": @(path),
            @"cwd": NSFileManager.defaultManager.currentDirectoryPath,
            @"environment": NSProcessInfo.processInfo.environment,
            @"bundlePath": bundle.bundlePath,
            @"gameMode": [bundle objectForInfoDictionaryKey:@"LSSupportsGameMode"] ?: @NO
        };
        NSData *json = [NSJSONSerialization dataWithJSONObject:data options:0 error:nil];
        write(STDOUT_FILENO, json.bytes, json.length);
        if (getenv("PROBE_SLEEP")) sleep(10);
        exit(0);
    }
}
