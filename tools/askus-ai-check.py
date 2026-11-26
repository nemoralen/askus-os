#!/usr/bin/env python3
"""Run ASKus AI (no window) and check: model verified + loaded, Knowledge used, a full chat
streams, the secret is enforced, and there is no network. Usage: askus-ai-check.py DATA ENGINE"""
import json, socket, subprocess, sys, time, urllib.request
data, engine = sys.argv[1], sys.argv[2]
p = subprocess.Popen([sys.executable, "-I", "/usr/local/lib/askus-ai/app/app.py", "--data", data, "--engine", engine,
                      "--window", "none"], stdout=subprocess.PIPE, text=True)
u = p.stdout.readline().strip()
op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
try:
    for _ in range(300):
        s = json.load(op.open(u + "api/state"))
        if s["model"] or s["status"].startswith("Problem"):
            break
        time.sleep(1)
    print("status:", s["status"])
    assert s["model"] == "qwen3-4b", s["status"]
    assert s["knowledge"]["files"] == 1
    out = op.open(urllib.request.Request(u + "api/chat", data=b'{"text":"What plywood do cabinet boxes use?"}',
                                         headers={"Content-Type": "application/json"})).read().decode()
    assert '"type": "sources"' in out and '"type": "done"' in out, out[:500]
    try:
        op.open(u.rsplit("/", 2)[0] + "/wrong/api/state"); raise AssertionError("wrong secret accepted")
    except urllib.error.HTTPError as e:
        assert e.code == 404
    try:
        socket.create_connection(("1.1.1.1", 443), timeout=5); raise AssertionError("network reachable")
    except OSError:
        pass
    print("chat, knowledge, secret and no-network checks passed")
finally:
    p.terminate(); p.wait(15)
