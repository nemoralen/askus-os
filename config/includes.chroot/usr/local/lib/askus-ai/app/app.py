#!/usr/bin/env python3
"""ASKus AI: a private AI that runs entirely on this computer.

    app.py --data DIR --engine DIR [--window askus|edge|none]

Starts a small web server on 127.0.0.1 (random port, random secret in the address) that
serves the chat window, starts llama-server with the best verified model for this
computer, and opens the window: the offline ASKus app window in ASKus OS, an Edge app
window on Windows. Closing the window stops everything."""
import argparse
import json
import os
import secrets
import shutil
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
VERSION = "1.0"


class State:
    def __init__(self, paths):
        self.paths = paths
        self.models = core.Models(paths)
        self.engine = core.Engine(paths)
        self.knowledge = core.Knowledge(paths.knowledge)
        self.chat = core.Chat()
        self.answers = []             # per assistant message: {"context": [...], "answer": "..."}
        self.status = "Starting…"
        self.busy = False
        self.ram = core.ram_gb()
        self.gpus = []
        self.progress = None
        self.lock = threading.Lock()

    def snapshot(self):
        return {
            "version": VERSION,
            "status": self.status,
            "busy": self.busy,
            "progress": self.progress,
            "engine": self.engine.info if self.engine.running() else "",
            "model": self.engine.model_id if self.engine.running() else None,
            "models": self.models.status(),
            "ram_gb": round(self.ram, 1),
            "gpus": self.gpus,
            "knowledge": {"files": self.knowledge.files, "chunks": len(self.knowledge.chunks),
                          "skipped": self.knowledge.skipped[:20]},
            "folders": {"data": self.paths.data, "models": self.paths.models,
                        "knowledge": self.paths.knowledge, "chats": self.paths.chats,
                        "feedback": self.paths.feedback},
            "messages": len(self.chat.messages),
            "platform": "windows" if core.IS_WIN else "askus",
        }

    def startup(self):
        try:
            self.status = "Checking this computer…"
            self.gpus = core.gpu_devices(self.paths.server_bin)
            self.status = "Reading your Knowledge folder…"
            self.knowledge.rebuild()
            st = self.models.status()
            for s in st:
                if s["present"] and not s["verified"] and s["why"] == "not checked yet":
                    self.verify(s["id"])
            st = self.models.status()
            best = core.pick_model(st, self.models.registry, self.ram, self.gpus)
            if not best:
                missing = not any(s["present"] for s in st)
                self.status = ("No AI model installed yet - see Settings for how to add one."
                               if missing else "No verified model - see Settings.")
                return
            self.load(best)
        except Exception as e:      # shown in the window
            self.status = "Problem: " + str(e)
            self.busy = False

    def verify(self, model_id):
        m = self.models.get(model_id)
        self.busy = True
        self.status = f"Checking the fingerprint of {m['name']}…"

        def prog(done, total):
            self.progress = round(100 * done / total)
        ok, why = self.models.verify(model_id, prog)
        self.progress = None
        self.busy = False
        self.status = f"{m['name']}: {why}"
        return ok, why

    def load(self, model_id):
        m = self.models.get(model_id)
        if not m:
            raise ValueError("unknown model")
        if not next(s for s in self.models.status() if s["id"] == model_id)["verified"]:
            ok, why = self.verify(model_id)
            if not ok:
                raise RuntimeError(why)
        self.busy = True
        self.status = f"Loading {m['name']}…"
        try:
            info = self.engine.start(m, self.gpus)
            self.status = "Ready · " + info
        finally:
            self.busy = False
        self.new_chat()

    def new_chat(self):
        self.chat = core.Chat()
        self.answers = []


def make_handler(state, token):
    ui_path = os.path.join(HERE, "ui.html")

    class H(BaseHTTPRequestHandler):
        server_version = "ASKusAI"

        def log_message(self, *_a):
            pass

        def _ok_path(self):
            # Every request must carry the secret, and come from this computer's own page
            if not self.path.startswith(f"/{token}/"):
                self.send_error(404)
                return None
            origin = self.headers.get("Origin")
            if origin and not origin.startswith(f"http://127.0.0.1:{self.server.server_port}"):
                self.send_error(403)
                return None
            return self.path[len(token) + 1:]

        def _json(self, obj, code=200):
            data = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _body(self):
            n = int(self.headers.get("Content-Length") or 0)
            if n > 2_000_000:
                return {}
            try:
                return json.loads(self.rfile.read(n) or b"{}")
            except ValueError:
                return {}

        def do_GET(self):
            p = self._ok_path()
            if p is None:
                return
            if p in ("/", "/index.html"):
                with open(ui_path, "rb") as f:
                    data = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Security-Policy",
                                 "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
                                 "connect-src 'self'; img-src data:")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(data)
            elif p == "/api/state":
                self._json(state.snapshot())
            else:
                self.send_error(404)

        def do_POST(self):
            p = self._ok_path()
            if p is None:
                return
            b = self._body()
            try:
                if p == "/api/chat":
                    return self._chat(b)
                if p == "/api/load":
                    if state.busy:
                        return self._json({"error": "busy"}, 409)
                    threading.Thread(target=self._safe, args=(state.load, b.get("id")), daemon=True).start()
                    return self._json({"ok": True})
                if p == "/api/verify":
                    if state.busy:
                        return self._json({"error": "busy"}, 409)
                    threading.Thread(target=self._safe, args=(state.verify, b.get("id")), daemon=True).start()
                    return self._json({"ok": True})
                if p == "/api/new":
                    state.new_chat()
                    return self._json({"ok": True})
                if p == "/api/save":
                    if not state.chat.messages:
                        return self._json({"error": "Nothing to save yet."}, 400)
                    path = core.save_chat(state.chat, state.paths.chats)
                    return self._json({"ok": True, "path": path})
                if p == "/api/feedback":
                    i = int(b.get("index", -1))
                    if not 0 <= i < len(state.answers):
                        return self._json({"error": "unknown answer"}, 400)
                    a = state.answers[i]
                    core.log_feedback(state.paths.feedback, state.engine.model_id, a["context"], a["answer"],
                                      "up" if b.get("rating") == "up" else "down",
                                      str(b.get("correction", ""))[:20000])
                    return self._json({"ok": True})
                if p == "/api/reindex":
                    f, c, skipped = state.knowledge.rebuild()
                    return self._json({"ok": True, "files": f, "chunks": c, "skipped": skipped})
                if p == "/api/open":
                    return self._json({"ok": open_folder(state.snapshot()["folders"].get(b.get("what"), ""))})
            except Exception as e:
                return self._json({"error": str(e)}, 500)
            self.send_error(404)

        def _safe(self, fn, *a):
            try:
                fn(*a)
            except Exception as e:
                state.status = "Problem: " + str(e)
                state.busy = False

        def _chat(self, b):
            text = str(b.get("text", "")).strip()[:50000]
            if not text:
                return self._json({"error": "empty"}, 400)
            if not state.engine.running():
                return self._json({"error": "No model is loaded yet."}, 409)
            if not state.lock.acquire(blocking=False):
                return self._json({"error": "Still answering the last question."}, 409)
            try:
                notes = state.knowledge.search(text) if b.get("knowledge", True) else []
                msgs = core.build_messages(state.chat, text, notes, bool(b.get("think")))
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()

                def ev(obj):
                    self.wfile.write(b"data: " + json.dumps(obj).encode() + b"\n\n")
                    self.wfile.flush()
                if notes:
                    ev({"type": "sources", "sources": [src for src, _t in notes]})
                full = ""
                for piece in state.engine.stream_chat(msgs, 0.6 if b.get("think") else 0.7):
                    full += piece
                    ev({"type": "token", "text": piece})
                answer = core.strip_thinking(full)
                state.chat.messages += [{"role": "user", "content": text},
                                        {"role": "assistant", "content": answer}]
                state.answers.append({"context": msgs[1:-1] + [msgs[-1]], "answer": answer})
                ev({"type": "done", "index": len(state.answers) - 1, "answer": answer})
            except (BrokenPipeError, ConnectionResetError):
                pass
            except Exception as e:
                try:
                    self.wfile.write(b"data: " + json.dumps({"type": "error", "text": str(e)}).encode() + b"\n\n")
                except OSError:
                    pass
            finally:
                state.lock.release()

    return H


def open_folder(path):
    if not path or not os.path.isdir(path):
        return False
    try:
        if core.IS_WIN:
            os.startfile(path)   # noqa: S606 - user's own folder
            return True
        # Inside the ASKus sandbox there's no file manager; the window shows the path instead
        return False
    except OSError:
        return False


def find_edge():
    for base in (os.environ.get("ProgramFiles(x86)", ""), os.environ.get("ProgramFiles", ""),
                 os.environ.get("LOCALAPPDATA", "")):
        p = os.path.join(base, "Microsoft", "Edge", "Application", "msedge.exe")
        if os.path.isfile(p):
            return p
    return shutil.which("msedge") or ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, help="folder for Models, Knowledge, Chats, Feedback")
    ap.add_argument("--engine", required=True, help="folder that contains llama-server")
    ap.add_argument("--window", default="none", choices=["askus", "edge", "none"])
    ap.add_argument("--require-offline", action="store_true",
                    help="refuse to start unless loopback is the only network interface (ASKus sandbox)")
    a = ap.parse_args()
    if a.require_offline:
        try:
            with open("/proc/self/net/dev") as f:  # always this process's own network namespace
                nics = sorted(l.split(":")[0].strip() for l in f.readlines()[2:] if ":" in l)
        except OSError:
            nics = ["?"]
        if nics != ["lo"]:
            print("ASKus AI: refusing to start, network interfaces visible: " + ", ".join(nics), file=sys.stderr)
            sys.exit(3)

    paths = core.Paths(a.data, a.engine)
    state = State(paths)
    # Stop the engine however the app ends (window closed, Ctrl+C, killed, logout)
    import atexit
    import signal
    atexit.register(state.engine.stop)

    def _quit(*_a):
        raise KeyboardInterrupt
    for sig in ("SIGTERM", "SIGHUP"):
        if hasattr(signal, sig):
            signal.signal(getattr(signal, sig), _quit)
    token = secrets.token_urlsafe(24)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(state, token))
    srv.daemon_threads = True
    url = f"http://127.0.0.1:{srv.server_port}/{token}/"
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    threading.Thread(target=state.startup, daemon=True).start()

    try:
        if a.window == "askus":
            subprocess.run(["/usr/local/bin/askus-appwindow", "--id", "askus-ai", "--title", "ASKus AI",
                            "--icon", "/usr/share/icons/hicolor/scalable/apps/askus-ai.svg", url])
        elif a.window == "edge":
            edge = find_edge()
            if not edge:
                import webbrowser
                webbrowser.open(url)
                input("ASKus AI is open in your browser. Press Enter here to quit.\n")
            else:
                profile = os.path.join(a.data, ".window")
                subprocess.run([edge, f"--app={url}", f"--user-data-dir={profile}", "--no-first-run",
                                "--no-default-browser-check", "--disable-extensions", "--disable-sync",
                                "--window-size=980,820"])
        else:
            print(url, flush=True)
            while True:
                time.sleep(3600)
    except KeyboardInterrupt:
        pass
    finally:
        state.engine.stop()
        srv.shutdown()


if __name__ == "__main__":
    main()
