#!/usr/bin/env bash
# Re-render all branding PNGs from the SVG sources (needs librsvg2-bin + fonts-inter).
set -euo pipefail
cd "$(dirname "$0")"
[ -f logo.svg ] || bash src/make-logo.sh
python3 make-graphics.py
mkdir -p png
for s in 16 24 32 48 64; do rsvg-convert -w $s -h $s logo-small.svg -o png/askus-logo-$s.png; done
for s in 128 256 512 1024; do rsvg-convert -w $s -h $s logo.svg -o png/askus-logo-$s.png; done
rsvg-convert -w 2000 logo-wordmark.svg          -o png/askus-wordmark.png
rsvg-convert -w 2000 logo-wordmark-light.svg    -o png/askus-wordmark-light.png
rsvg-convert -w 2000 logo-wordmark-on-dark.svg  -o png/askus-wordmark-on-dark.png
rsvg-convert -w 800  logo-wordmark.svg          -o png/askus-wordmark-800.png
rsvg-convert -w 3840 -h 2160 wallpaper.svg      -o png/askus-wallpaper.png
rsvg-convert -w 1920 -h 1080 boot-splash.svg    -o png/grub-splash.png
rsvg-convert -w 640  -h 480 -a boot-splash.svg  -o /tmp/isl.png 2>/dev/null || true
# isolinux needs exactly 640x480: crop centre of a 853x480 render
rsvg-convert -w 853 -h 480 boot-splash.svg -o /tmp/isl.png
convert /tmp/isl.png -gravity center -crop 640x480+0+0 +repage png/isolinux-splash.png
echo "Rendered into $(pwd)/png"
