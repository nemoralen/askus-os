#!/usr/bin/env bash
# Build the ASKus OS ISO. Run as root on Debian 13 (trixie), or let GitHub Actions do it.
#   sudo ./build.sh            -> askus-os-amd64.hybrid.iso
set -euo pipefail
cd "$(dirname "$0")"
[ "$(id -u)" = 0 ] || { echo "Run as root: sudo ./build.sh"; exit 1; }

echo "==> Installing build tools"
apt-get update
apt-get install -y --no-install-recommends live-build debootstrap xorriso squashfs-tools \
  mtools dosfstools grub-efi-amd64-bin grub-pc-bin shim-signed grub-efi-amd64-signed \
  syslinux syslinux-common isolinux librsvg2-bin imagemagick ca-certificates git curl python3 rsync

echo "==> Stamping version"
ASKUS_BUILD_ID=${ASKUS_BUILD_ID:-$(date -u +%Y%m%d%H%M)}
ASKUS_UPDATE_REPO=${ASKUS_UPDATE_REPO:-nemoralen/askus-os}
cat > config/includes.chroot/etc/askus-release <<REL
VERSION=1.0
BUILD_ID=$ASKUS_BUILD_ID
TAG=v1.0-$ASKUS_BUILD_ID
UPDATE_REPO=$ASKUS_UPDATE_REPO
REL
cat config/includes.chroot/etc/askus-release

echo "==> Rendering branding (logo, icons, wallpaper, boot splash)"
apt-get install -y --no-install-recommends librsvg2-bin imagemagick fonts-inter fonts-dejavu-core
bash branding/render.sh
P=config/includes.chroot/usr/share/plymouth/themes/askus
rsvg-convert -w 260 -h 260 branding/logo.svg -o $P/logo.png
rsvg-convert branding/plymouth-wordmark.svg -o $P/wordmark.png
convert -size 12x12 xc:none -fill '#C4B5FD' -draw 'circle 6,6 6,1' $P/dot.png

echo "==> Copying branding into the image"
B=config/includes.chroot/usr/share
mkdir -p $B/askus/png $B/backgrounds/askus
rsync -a branding/png/ $B/askus/png/
cp branding/logo.svg $B/askus/logo.svg
cp branding/png/askus-wallpaper.png $B/backgrounds/askus/askus-wallpaper.png
mkdir -p config/includes.chroot/usr/share/askus

echo "==> Checking that every package exists in Debian (missing ones are skipped, not fatal)"
cat > /tmp/askus-sources.list <<SRC
deb http://deb.debian.org/debian trixie main contrib non-free non-free-firmware
deb http://deb.debian.org/debian trixie-updates main contrib non-free non-free-firmware
deb http://security.debian.org/debian-security trixie-security main contrib non-free non-free-firmware
SRC
APTOPT=(-o Dir::Etc::SourceList=/tmp/askus-sources.list -o Dir::Etc::SourceParts=/dev/null
        -o Dir::State::Lists=/tmp/askus-lists -o APT::Architecture=amd64)
mkdir -p /tmp/askus-lists/partial
apt-get "${APTOPT[@]}" update -qq
for list in config/package-lists/*.list.chroot; do
  while read -r pkg; do
    case "$pkg" in ""|\#*) continue;; esac
    if ! apt-cache "${APTOPT[@]}" show "$pkg" >/dev/null 2>&1; then
      echo "   ! $pkg not found in trixie - skipping it"
      sed -i "s/^$pkg\$/# MISSING: $pkg/" "$list"
    fi
  done < <(cat "$list")
done

echo "==> Configuring live-build"
lb clean --purge >/dev/null 2>&1 || true
lb config

echo "==> Branding the boot menu"
rm -rf config/bootloaders
cp -r /usr/share/live/build/bootloaders config/bootloaders
find config/bootloaders -name 'splash.png' | while read -r f; do
  case "$f" in *isolinux*|*syslinux*) cp branding/png/isolinux-splash.png "$f";; *) cp branding/png/grub-splash.png "$f";; esac
done
for f in $(find config/bootloaders -name 'splash.svg*'); do
  # isolinux renders its splash from this SVG; embed our 640x480 artwork
  printf '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="640" height="480"><image width="640" height="480" xlink:href="data:image/png;base64,%s"/></svg>\n' \
    "$(base64 -w0 branding/png/isolinux-splash.png)" > "$f"
done
grep -rl "Live system" config/bootloaders 2>/dev/null | xargs -r sed -i 's/Live system/ASKus OS/g'

echo "==> Building (this takes 30-60 minutes)"
lb build 2>&1 | tee build.log
ISO=$(ls -1 *.iso | head -n1)
sha256sum "$ISO" > "$ISO.sha256"
echo "==> Done: $ISO ($(du -h "$ISO" | cut -f1))"
