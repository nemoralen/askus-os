#!/usr/bin/env bash
# Regenerates branding/logo.svg (official "final-v4-hightech") and branding/logo-small.svg
# from the generator scripts. Output is deterministic (fixed random seeds).
set -euo pipefail
SRC="$(cd "$(dirname "$0")" && pwd)"; OUT="$SRC/.."
T=$(mktemp -d); cd "$T"
python3 "$SRC/logo_base.py"
python3 "$SRC/logo_compose.py"
cp final-v4-hightech.svg "$OUT/logo.svg"
python3 - "$SRC/logo_compose.py" "$OUT/logo-small.svg" <<'PY'
import sys
src=open(sys.argv[1]).read().replace('for k,v in V.items(): open(k+".svg","w").write(v)','')
exec(src)
open(sys.argv[2],"w").write(compose(42, rim='stroke="url(#rimn)" stroke-opacity="0.9" stroke-width="10"', splat_scale=0.5))
PY
rm -rf "$T"
