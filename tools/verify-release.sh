#!/bin/bash
# Check an ASKus OS release with nothing but this repository and the release files.
#   tools/verify-release.sh DIR
# DIR holds the files from one GitHub release: the .iso (or .iso.part00/.part01...),
# SHA256SUMS, SHA256SUMS.sig, MANIFEST and MANIFEST.sig.
# Checks: both signatures are from the ASKus release key in config/includes.chroot/etc/askus/
# release-signers, the image matches SHA256SUMS, and every file inside the image matches
# MANIFEST. If you rebuilt the same commit yourself, compare your MANIFEST with this one:
#   diff <(grep '^P ' yours/MANIFEST) <(grep '^P ' DIR/MANIFEST)   (package versions)
set -euo pipefail
DIR=${1:?usage: tools/verify-release.sh DIR}
SIGNERS="$(cd "$(dirname "$0")/.." && pwd)/config/includes.chroot/etc/askus/release-signers"
ok() { echo "  OK   $*"; }
fail() { echo "  FAIL $*"; exit 1; }
cd "$DIR"

echo "1. Signatures"
ssh-keygen -Y verify -f "$SIGNERS" -I askus-release -n askus-release -s SHA256SUMS.sig < SHA256SUMS >/dev/null 2>&1 \
  && ok "SHA256SUMS is signed by the ASKus release key" || fail "SHA256SUMS signature"
ssh-keygen -Y verify -f "$SIGNERS" -I askus-release -n askus-manifest -s MANIFEST.sig < MANIFEST >/dev/null 2>&1 \
  && ok "MANIFEST is signed by the ASKus release key" || fail "MANIFEST signature"

read -r WANT NAME < SHA256SUMS
[ "$(sed -n 2p MANIFEST)" = "build $NAME" ] && ok "MANIFEST belongs to $NAME" || fail "MANIFEST is for another build"

echo "2. Image"
if [ ! -f "$NAME" ] && ls "$NAME".part* >/dev/null 2>&1; then cat "$NAME".part* > "$NAME"; fi
GOT=$(sha256sum < "$NAME" | cut -d' ' -f1)
[ "$GOT" = "$WANT" ] && ok "$NAME matches SHA256SUMS" || fail "$NAME does not match SHA256SUMS"

echo "3. Files inside the image"
command -v xorriso >/dev/null || { echo "  (install xorriso to check the files inside the image)"; exit 0; }
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
xorriso -osirrox on -indev "$NAME" -extract / "$T/iso" >/dev/null 2>&1
grep '^F ' MANIFEST | cut -c3- > "$T/want"
(cd "$T/iso" && find . -type f -print0 | sort -z | xargs -0 sha256sum) > "$T/got"
if diff -q "$T/want" "$T/got" >/dev/null; then
  ok "all $(wc -l < "$T/want") files match MANIFEST"
else
  diff "$T/want" "$T/got" | head -20; fail "files differ from MANIFEST"
fi
echo "All checks passed."
