/* Build: x86_64-w64-mingw32-gcc -O2 -Wall fullscreen.c -o fullscreen.exe -lgdi32
 * No keyboard synthesis or remapping. Physical key messages are logged verbatim.
 * YAAGL_TEST_SECONDS controls lifetime (default 90). Run in a disposable prefix.
 */
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
static unsigned ticks;
static HWND windows[12];
static const char *names[12];
static unsigned count;
static LRESULT CALLBACK proc(HWND hwnd, UINT msg, WPARAM wp, LPARAM lp)
{
    if (msg == WM_GETMINMAXINFO && GetWindowLongPtrA(hwnd,GWLP_USERDATA) == 1) {
        MINMAXINFO *m=(MINMAXINFO *)lp;
        RECT r={0,0,480,300};
        AdjustWindowRectEx(&r,GetWindowLongA(hwnd,GWL_STYLE),FALSE,GetWindowLongA(hwnd,GWL_EXSTYLE));
        m->ptMinTrackSize.x=m->ptMaxTrackSize.x=r.right-r.left;
        m->ptMinTrackSize.y=m->ptMaxTrackSize.y=r.bottom-r.top;
        return 0;
    }
    if (msg==WM_KEYDOWN || msg==WM_KEYUP || msg==WM_SYSKEYDOWN || msg==WM_SYSKEYUP) {
        printf("KEY hwnd=%p msg=%04x vk=%04llx lparam=%08llx\n",(void *)hwnd,msg,(unsigned long long)wp,(unsigned long long)lp);
        fflush(stdout);
    }
    if (msg==WM_PAINT) {
        PAINTSTRUCT ps; char title[100];
        HDC dc=BeginPaint(hwnd,&ps); GetWindowTextA(hwnd,title,sizeof(title));
        TextOutA(dc,16,16,title,lstrlenA(title));
        const char *hint="Native fullscreen test; physical keys are logged.";
        TextOutA(dc,16,44,hint,lstrlenA(hint));
        EndPaint(hwnd,&ps); return 0;
    }
    if (msg==WM_CLOSE) { DestroyWindow(hwnd); return 0; }
    return DefWindowProcA(hwnd,msg,wp,lp);
}
static HWND add(const char *name,DWORD style,DWORD ex,HWND parent,const char *cls)
{
    RECT r={0,0,480,300};
    AdjustWindowRectEx(&r,style,FALSE,ex);
    HWND w=CreateWindowExA(ex,cls,name,style,80+count*25,80+count*22,r.right-r.left,r.bottom-r.top,parent,NULL,GetModuleHandle(NULL),NULL);
    if (!w) { fprintf(stderr,"CreateWindow %s failed %lu\n",name,GetLastError()); exit(2); }
    windows[count]=w; names[count++]=name; ShowWindow(w,SW_SHOWNOACTIVATE); return w;
}
int main(void)
{
    SetProcessDPIAware();
    WNDCLASSA cls={0}; cls.lpfnWndProc=proc; cls.hInstance=GetModuleHandle(NULL);
    cls.lpszClassName="YAAGLFullscreenTest"; cls.hCursor=LoadCursor(NULL,IDC_ARROW);
    cls.hbrBackground=(HBRUSH)(COLOR_WINDOW+1); RegisterClassA(&cls);
    DWORD fixed=WS_OVERLAPPED|WS_CAPTION|WS_SYSMENU|WS_MINIMIZEBOX;
    HWND main=add("YAAGL fixed",fixed,0,NULL,cls.lpszClassName);
    if (!getenv("YAAGL_TEST_UNCONSTRAINED")) SetWindowLongPtrA(main,GWLP_USERDATA,1);
    add("YAAGL resizable",WS_OVERLAPPEDWINDOW,0,NULL,cls.lpszClassName);
    add("YAAGL fixed-max",fixed|WS_MAXIMIZEBOX,0,NULL,cls.lpszClassName);
    add("YAAGL owned",fixed,0,main,cls.lpszClassName);
    add("YAAGL tool",fixed,WS_EX_TOOLWINDOW,NULL,cls.lpszClassName);
    add("YAAGL popup",fixed|WS_POPUP,0,NULL,cls.lpszClassName);
    add("YAAGL dialog",WS_POPUP|WS_CAPTION|WS_SYSMENU,WS_EX_DLGMODALFRAME,main,"#32770");
    add("YAAGL ownerless-dialog",fixed,0,NULL,"#32770");
    add("YAAGL noactivate",fixed,WS_EX_NOACTIVATE,NULL,cls.lpszClassName);
    add("YAAGL child",WS_CHILD|WS_BORDER,0,main,cls.lpszClassName);
    add("YAAGL disabled",fixed|WS_DISABLED,0,NULL,cls.lpszClassName);
    add("YAAGL constrained",WS_OVERLAPPEDWINDOW,0,NULL,cls.lpszClassName);
    SetWindowLongPtrA(windows[count-1],GWLP_USERDATA,1);
    SetForegroundWindow(main);
    unsigned seconds=getenv("YAAGL_TEST_SECONDS") ? atoi(getenv("YAAGL_TEST_SECONDS")) : 90;
    UINT_PTR timer=SetTimer(NULL,0,1000,NULL);
    MSG msg;
    while (GetMessageA(&msg,NULL,0,0)>0) {
        if (msg.message==WM_TIMER && msg.wParam==timer) {
            for (unsigned i=0;i<count;i++) {
                RECT r,c; GetWindowRect(windows[i],&r); GetClientRect(windows[i],&c);
                printf("RECT t=%u name=%s window=%ld,%ld,%ld,%ld client=%ld,%ld style=%08lx ex=%08lx\n",ticks,names[i],r.left,r.top,r.right-r.left,r.bottom-r.top,c.right,c.bottom,(unsigned long)GetWindowLongA(windows[i],GWL_STYLE),(unsigned long)GetWindowLongA(windows[i],GWL_EXSTYLE));
            }
            fflush(stdout);
            if (++ticks>=seconds) break;
        }
        TranslateMessage(&msg); DispatchMessageA(&msg);
    }
    for (unsigned i=0;i<count;i++) if (IsWindow(windows[i])) DestroyWindow(windows[i]);
    return 0;
}
