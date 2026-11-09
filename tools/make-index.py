#!/usr/bin/env python3
"""Write the delta-update index of an ASKus OS image.

  make-index.py IMAGE.iso OUT.index.gz /path/to/askus-cdc

Format (gzip text):  askus-delta-index 1 <image name> <size>
                     <offset> <length> <sha256>   (one line per chunk)
The updater matches these SHA-256 fingerprints against the image already on the USB
stick and downloads only the chunks that changed. Every re-used chunk is checked
against this fingerprint, and the finished image against the signed SHA256SUMS.
"""
import gzip
import hashlib
import os
import subprocess
import sys

iso, out, cdc = sys.argv[1:4]
total = os.path.getsize(iso)
cuts = subprocess.run([cdc, iso], capture_output=True, text=True, check=True).stdout.split("\n")
lines = [f"askus-delta-index 1 {os.path.basename(iso)} {total}"]
pos = 0
with open(iso, "rb") as f:
    for line in cuts:
        if not line:
            continue
        o, n = map(int, line.split())
        assert o == pos, (o, pos)
        data = f.read(n)
        assert len(data) == n
        lines.append(f"{o} {n} {hashlib.sha256(data).hexdigest()}")
        pos += n
assert pos == total, (pos, total)
with open(out, "wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", compresslevel=9, mtime=0) as g:
    g.write(("\n".join(lines) + "\n").encode())
print(f"{len(lines) - 1} chunks, {total} bytes -> {out}")
