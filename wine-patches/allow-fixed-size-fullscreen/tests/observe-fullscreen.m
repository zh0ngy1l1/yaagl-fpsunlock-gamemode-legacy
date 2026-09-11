/* Test-only Cocoa observer. Invoke toggleFullScreen: directly; never synthesize keys.
 * Build: clang -arch x86_64 -dynamiclib -framework Cocoa observe-fullscreen.m -o observe-fullscreen.dylib
 * Inject ONLY into the isolated fullscreen.exe test run with DYLD_INSERT_LIBRARIES.
 * Private Space queries are diagnostic only and are never part of the engine patch.
 */
#import <Cocoa/Cocoa.h>
#include <dlfcn.h>
static FILE *logfile;
static int stage, ticks;
static NSWindow *target;
static NSRect savedFrame;
static int failures;
static int (*connectionID)(void);
static CFArrayRef (*copySpaces)(int,int,CFArrayRef);
static int (*spaceType)(int,uint64_t);
static BOOL inFullscreenSpace(NSWindow *w)
{
    if (!connectionID || !copySpaces || !spaceType) return NO;
    CFArrayRef spaces=copySpaces(connectionID(),7,(__bridge CFArrayRef)@[@(w.windowNumber)]);
    BOOL found=NO;
    for (NSNumber *s in (__bridge NSArray *)spaces) if (spaceType(connectionID(),s.unsignedLongLongValue)==4) found=YES;
    if (spaces) CFRelease(spaces);
    return found;
}
static void snapshot(NSWindow *w,const char *phase)
{
    fprintf(logfile,"SNAP %s title=%s style=%lx behavior=%lx frame=%s min=%s max=%s active=%d space4=%d zoom=%d\n",phase,w.title.UTF8String,(unsigned long)w.styleMask,(unsigned long)w.collectionBehavior,NSStringFromRect(w.frame).UTF8String,NSStringFromSize(w.contentMinSize).UTF8String,NSStringFromSize(w.contentMaxSize).UTF8String,w.onActiveSpace,inFullscreenSpace(w),[w standardWindowButton:NSWindowZoomButton].enabled);
    fflush(logfile);
}
static void check(BOOL value,const char *what)
{
    fprintf(logfile,"%s %s\n",value ? "PASS" : "FAIL",what);
    if (!value) failures++;
    fflush(logfile);
}
static NSWindow *find(NSString *title)
{
    for (NSWindow *w in NSApp.windows) if ([w.title isEqualToString:title]) return w;
    return nil;
}
static void step(void)
{
    if (!find(@"YAAGL constrained")) return;
    if (++ticks%8) return; /* four seconds per transition, no busy polling */
    BOOL enabled=getenv("YAAGL_EXPECT_FIXED") && atoi(getenv("YAAGL_EXPECT_FIXED"));
    if (!stage) {
        for (NSWindow *w in NSApp.windows) if ([w.title hasPrefix:@"YAAGL "]) snapshot(w,"initial");
        check(!!(find(@"YAAGL fixed").collectionBehavior & NSWindowCollectionBehaviorFullScreenPrimary)==enabled,"fixed eligibility matches setting");
        check(!(find(@"YAAGL fixed").styleMask & NSWindowStyleMaskResizable),"fixed Cocoa style remains nonresizable");
        check([find(@"YAAGL fixed") standardWindowButton:NSWindowZoomButton].enabled==enabled,"fixed green button matches setting");
        check(!!(find(@"YAAGL resizable").collectionBehavior & NSWindowCollectionBehaviorFullScreenPrimary),"resizable eligibility retained");
        for (NSString *s in @[@"YAAGL owned",@"YAAGL tool",@"YAAGL popup",@"YAAGL dialog",@"YAAGL ownerless-dialog",@"YAAGL noactivate"])
            check(find(s) && !(find(s).collectionBehavior & NSWindowCollectionBehaviorFullScreenPrimary),s.UTF8String);
        check(!find(@"YAAGL child"),"child has no Cocoa top-level window");
        target=[find(enabled ? @"YAAGL fixed" : @"YAAGL resizable") retain]; savedFrame=target.frame;
        [target makeKeyAndOrderFront:nil]; [NSApp activateIgnoringOtherApps:YES];
        snapshot(target,"before-enter"); [target toggleFullScreen:nil];
    } else if (stage==1 || stage==3 || stage==5) {
        snapshot(target,"entered");
        check(!!(target.styleMask & NSWindowStyleMaskFullScreen),"Cocoa native fullscreen style set");
        check(inFullscreenSpace(target),"window belongs to an actual fullscreen Space (type 4)");
        [target toggleFullScreen:nil];
    } else if (stage==2 || stage==4 || stage==6) {
        snapshot(target,"exited");
        check(!(target.styleMask & NSWindowStyleMaskFullScreen),"Cocoa native fullscreen style cleared");
        check(!inFullscreenSpace(target),"window left fullscreen Space");
        check(NSEqualRects(savedFrame,target.frame),"windowed frame restored exactly");
        if (enabled) check(!(target.styleMask & NSWindowStyleMaskResizable),"fixed Cocoa style restored without resize permission");
        if (stage!=6) [target toggleFullScreen:nil];
        else {
            [target release]; target=[find(@"YAAGL resizable") retain]; savedFrame=target.frame;
            [target makeKeyAndOrderFront:nil]; [target toggleFullScreen:nil];
        }
    } else if (stage==7) {
        snapshot(target,"resizable-entered");
        check(!!(target.styleMask & NSWindowStyleMaskFullScreen) && inFullscreenSpace(target),"resizable still enters native fullscreen Space");
        [target toggleFullScreen:nil];
    } else if (stage==8) {
        snapshot(target,"resizable-exited");
        check(!(target.styleMask & NSWindowStyleMaskFullScreen) && NSEqualRects(savedFrame,target.frame),"resizable exits and restores frame");
        [target release]; target=[find(@"YAAGL fixed-max") retain]; savedFrame=target.frame;
        [target makeKeyAndOrderFront:nil]; [target toggleFullScreen:nil];
    } else if (stage==9) {
        snapshot(target,"fixed-max-entered");
        check(!!(target.styleMask & NSWindowStyleMaskFullScreen) && inFullscreenSpace(target),"fixed maximize-box window enters native Space");
        [target toggleFullScreen:nil];
    } else if (stage==10) {
        snapshot(target,"fixed-max-exited");
        check(!(target.styleMask & NSWindowStyleMaskFullScreen) && NSEqualRects(savedFrame,target.frame),"fixed maximize-box window restores frame");
        check(NSEqualSizes(target.contentMinSize,target.contentMaxSize),"fixed maximize-box window retains fixed constraints");
        [target release]; target=[find(@"YAAGL constrained") retain]; savedFrame=target.frame;
        [target makeKeyAndOrderFront:nil]; [target toggleFullScreen:nil];
    } else if (stage==11) {
        snapshot(target,"constrained-entered");
        check(!!(target.styleMask & NSWindowStyleMaskFullScreen) && inFullscreenSpace(target),"constrained resizable window enters native Space");
        check(NSEqualSizes(target.contentMinSize,target.contentMaxSize),"application min/max constraints retained");
        [target toggleFullScreen:nil];
    } else if (stage==12) {
        snapshot(target,"constrained-exited");
        check(!(target.styleMask & NSWindowStyleMaskFullScreen) && NSEqualRects(savedFrame,target.frame),"constrained window restores frame");
        NSWindow *disabled=find(@"YAAGL disabled"); [disabled toggleFullScreen:nil];
        check(!(disabled.styleMask & NSWindowStyleMaskFullScreen),"disabled window cannot enter fullscreen");
        fprintf(logfile,"RESULT failures=%d\n",failures); fflush(logfile);
    }
    stage++;
}
__attribute__((constructor)) static void start(void)
{
    const char *path=getenv("YAAGL_OBSERVER_LOG");
    if (!path) return;
    logfile=fopen(path,"a"); if (!logfile) return;
    connectionID=dlsym(RTLD_DEFAULT,"CGSMainConnectionID");
    copySpaces=dlsym(RTLD_DEFAULT,"CGSCopySpacesForWindows");
    spaceType=dlsym(RTLD_DEFAULT,"CGSSpaceGetType");
    dispatch_async(dispatch_get_main_queue(),^{
        dispatch_source_t timer=dispatch_source_create(DISPATCH_SOURCE_TYPE_TIMER,0,0,dispatch_get_main_queue());
        dispatch_source_set_timer(timer,dispatch_time(DISPATCH_TIME_NOW,NSEC_PER_SEC),NSEC_PER_SEC/2,NSEC_PER_SEC/10);
        dispatch_source_set_event_handler(timer,^{@autoreleasepool { if(stage<=12) step(); }});
        dispatch_resume(timer);
    });
}
