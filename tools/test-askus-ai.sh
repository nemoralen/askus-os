#!/bin/bash
# Test ASKus AI in Debian 13 (used by .github/workflows/test-askus-ai.yml):
# build the engine exactly as the ISO hook does, then run the app with a tiny random
# GGUF model (no download) inside a no-network sandbox and check a full chat works.
set -euxo pipefail
REPO=$(cd "$(dirname "$0")/.." && pwd)
INC=$REPO/config/includes.chroot
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -y -q --no-install-recommends git ca-certificates python3 python3-numpy firejail poppler-utils

# 1. the hook, with its file paths pointed at this checkout
mkdir -p /usr/local/lib/askus-ai /usr/local/bin
cp "$INC/usr/local/lib/askus-ai/PINS" /usr/local/lib/askus-ai/
cp -r "$INC/usr/local/lib/askus-ai/app" /usr/local/lib/askus-ai/
cp "$INC/usr/local/bin/askus-ai" /usr/local/bin/
bash "$REPO/config/hooks/live/0490-askus-ai.hook.chroot" | tee /tmp/hook.log
grep -q "engine installed" /tmp/hook.log
E=/usr/local/lib/askus-ai/engine
"$E/llama-server" --version
"$E/llama-server" --list-devices
cat "$E/ASKUS-VERSION"

# 2. a tiny random model in GGUF format (made locally, nothing downloaded)
. /usr/local/lib/askus-ai/PINS
git clone -q --depth 1 --branch "$LLAMA_TAG" "$LLAMA_REPO" /tmp/lsrc
PYTHONPATH=/tmp/lsrc/gguf-py python3 "$REPO/tools/make-tiny-gguf.py" /tmp/lsrc/models/ggml-vocab-qwen2.gguf /tmp/tiny.gguf

# 3. run the app in the same sandbox settings as the launcher, as a normal user
useradd -m tester
D=/home/tester/data
mkdir -p "$D/Models" "$D/Knowledge"
cp /tmp/tiny.gguf "$D/Models/Qwen3-4B-Q4_K_M.gguf"
python3 -c "import hashlib,json,sys; h=hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest(); json.dump({'Qwen3-4B-Q4_K_M.gguf':h}, open(sys.argv[2],'w'))" \
  "$D/Models/Qwen3-4B-Q4_K_M.gguf" "$D/Models/hashes.json"
echo "Cabinet boxes use 3/4 inch plywood." > "$D/Knowledge/standards.md"
cp "$REPO/tools/askus-ai-check.py" /home/tester/
chown -R tester /home/tester
su tester -c "firejail --quiet --noprofile --net=none --whitelist=$D --whitelist=/home/tester/askus-ai-check.py \
  --private-tmp --caps.drop=all --nonewprivs --nogroups --noroot --seccomp \
  python3 -I /home/tester/askus-ai-check.py $D $E" || {
    echo "== app/engine log"; cat "$D/.engine.log" 2>/dev/null; exit 1; }
echo "ASKus AI test passed"
