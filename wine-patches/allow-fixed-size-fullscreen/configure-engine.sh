#!/bin/bash
# Configure the wine-11.0-fix Portfile's macOS 14+ x86_64 +gstreamer build.
set -euo pipefail
work=${YAAGL_WINE_WORK:-/Users/david/code/home/yaagl-wine-fullscreen}
export PATH="/opt/homebrew/opt/bison/bin:/opt/homebrew/bin:$PATH"
export MACOSX_DEPLOYMENT_TARGET=14.0
export CC='clang -arch x86_64'
export CXX='clang++ -arch x86_64'
export CFLAGS='-O2 -mmacosx-version-min=14.0'
export CROSSCFLAGS='-O2'
export CPPFLAGS="-I$work/deps/opt/local/include -I$work/runtime/lib/GStreamer.framework/Versions/1.0/include"
export LDFLAGS="-L$work/runtime/lib -Wl,-rpath,$work/runtime/lib"
export PKG_CONFIG_LIBDIR="$work/runtime/lib/GStreamer.framework/Versions/1.0/lib/pkgconfig"
export FREETYPE_CFLAGS="-I$work/runtime/lib/GStreamer.framework/Versions/1.0/include/freetype2"
export FREETYPE_LIBS="-L$work/runtime/lib -lfreetype"
export GNUTLS_CFLAGS="-I$work/deps/opt/local/include"
export GNUTLS_LIBS="-L$work/runtime/lib -lgnutls"
export SDL2_CFLAGS="-I$work/deps/opt/local/include/SDL2"
export SDL2_LIBS="-L$work/runtime/lib -lSDL2"
export INOTIFY_CFLAGS="-I$work/deps/libinotify-kqueue-20240724"
export INOTIFY_LIBS="-L$work/runtime/lib -linotify"
export FFMPEG_CFLAGS
export FFMPEG_LIBS
export GSTREAMER_CFLAGS
export GSTREAMER_LIBS
FFMPEG_CFLAGS=$(pkg-config --cflags libavutil libavformat libavcodec)
FFMPEG_LIBS=$(pkg-config --libs libavutil libavformat libavcodec)
GSTREAMER_CFLAGS=$(pkg-config --cflags gstreamer-1.0 gstreamer-video-1.0 gstreamer-audio-1.0 gstreamer-tag-1.0)
GSTREAMER_LIBS=$(pkg-config --libs gstreamer-1.0 gstreamer-video-1.0 gstreamer-audio-1.0 gstreamer-tag-1.0)
export ac_cv_lib_soname_vulkan=
mkdir -p "$work/build"
cd "$work/build"
exec "$work/wine-wine-11.0/configure" \
 --prefix="$work/dist/wine" --build=x86_64-apple-darwin25.6.0 --host=x86_64-apple-darwin25.6.0 \
 --enable-win64 --enable-archs=i386,x86_64 \
 --without-alsa --without-capi --with-coreaudio --with-cups --without-dbus \
 --with-ffmpeg --without-fontconfig --with-freetype --with-gettext --without-gettextpo \
 --without-gphoto --with-gnutls --without-gssapi --with-gstreamer --with-inotify \
 --without-krb5 --with-mingw --without-netapi --with-opencl --without-opengl \
 --without-oss --with-pcap --with-pcsclite --with-pthread --without-pulse \
 --without-sane --with-sdl --without-udev --with-unwind --without-usb --without-v4l2 \
 --with-vulkan --without-wayland --without-x --disable-tests \
 --disable-winebth_sys --disable-winemenubuilder
