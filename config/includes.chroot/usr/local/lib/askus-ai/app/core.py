"""ASKus AI core: local model engine (llama.cpp's llama-server), model checks, knowledge
search, chat history and feedback. Standard library only, so the same code runs in
ASKus OS (Linux, sandboxed with no network) and on Windows (test version)."""
import hashlib
import json
import math
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request

IS_WIN = os.name == "nt"
HERE = os.path.dirname(os.path.abspath(__file__))


# ---------------------------------------------------------------- folders
class Paths:
    def __init__(self, data_dir, engine_dir):
        self.data = data_dir
        self.models = os.path.join(data_dir, "Models")
        self.knowledge = os.path.join(data_dir, "Knowledge")
        self.chats = os.path.join(data_dir, "Chats")
        self.feedback = os.path.join(data_dir, "Feedback")
        self.engine_dir = engine_dir
        for d in (self.models, self.knowledge, self.chats, self.feedback):
            os.makedirs(d, exist_ok=True)

    @property
    def server_bin(self):
        name = "llama-server.exe" if IS_WIN else "llama-server"
        for c in (os.path.join(self.engine_dir, name), os.path.join(self.engine_dir, "bin", name)):
            if os.path.isfile(c):
                return c
        return shutil.which(name) or ""


# ---------------------------------------------------------------- models
def sha256_file(path, progress=None):
    h = hashlib.sha256()
    total = os.path.getsize(path)
    done = 0
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(8 << 20), b""):
            h.update(b)
            done += len(b)
            if progress:
                progress(done, total)
    return h.hexdigest()


class Models:
    """Known models (models.json, shipped with the app) and which of them are on disk and
    genuine. Only GGUF files are ever loaded (no pickle formats)."""

    def __init__(self, paths, registry=os.path.join(HERE, "models.json")):
        self.paths = paths
        with open(registry, encoding="utf-8") as f:
            self.registry = json.load(f)["models"]
        self.cache_file = os.path.join(paths.models, ".verified.json")
        self.local_hashes_file = os.path.join(paths.models, "hashes.json")   # written by Windows setup

    def _load(self, path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}

    def expected_hash(self, m):
        """The pinned hash; until a model is pinned, the hash recorded by the verified
        download (setup checked it against the hash Hugging Face publishes)."""
        if m.get("sha256"):
            return m["sha256"].lower(), "pinned"
        h = self._load(self.local_hashes_file).get(m["file"], "")
        return (h.lower(), "download") if re.fullmatch(r"[0-9a-fA-F]{64}", h or "") else ("", "")

    def status(self):
        """[{id, name, present, verified, why, size_gb}] - quick: uses a cache keyed on file
        size + modified time + change time, so the 2-9 GB files aren't re-hashed at every start."""
        cache = self._load(self.cache_file)
        out = []
        for m in self.registry:
            p = os.path.join(self.paths.models, m["file"])
            item = dict(id=m["id"], name=m["name"], file=m["file"], present=os.path.isfile(p),
                        verified=False, why="not installed", size_gb=m["approx_gb"])
            if item["present"]:
                st = os.stat(p)
                want, source = self.expected_hash(m)
                c = cache.get(m["file"], {})
                if not want:
                    item["why"] = "no known fingerprint for this file"
                elif (c.get("size"), c.get("mtime"), c.get("ctime"), c.get("sha256")) == (st.st_size, st.st_mtime_ns, st.st_ctime_ns, want):
                    item.update(verified=True, why=f"verified ({source})")
                else:
                    item["why"] = "not checked yet"
                item["size_gb"] = round(st.st_size / 1e9, 2)
            out.append(item)
        return out

    def verify(self, model_id, progress=None):
        m = next(x for x in self.registry if x["id"] == model_id)
        p = os.path.join(self.paths.models, m["file"])
        if not p.endswith(".gguf") or not os.path.isfile(p):
            return False, "file missing"
        with open(p, "rb") as f:
            if f.read(4) != b"GGUF":
                return False, "not a GGUF file"
        want, source = self.expected_hash(m)
        if not want:
            return False, "no known fingerprint for this file"
        got = sha256_file(p, progress)
        if got != want:
            return False, "FINGERPRINT MISMATCH - this file is not the genuine model"
        st = os.stat(p)
        cache = self._load(self.cache_file)
        # ctime changes on every write and (on Linux) can't be set back, unlike mtime
        cache[m["file"]] = {"size": st.st_size, "mtime": st.st_mtime_ns, "ctime": st.st_ctime_ns, "sha256": got}
        tmp = self.cache_file + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=1)
        os.replace(tmp, self.cache_file)
        return True, f"verified ({source})"

    def get(self, model_id):
        return next((x for x in self.registry if x["id"] == model_id), None)


# ---------------------------------------------------------------- hardware
def ram_gb():
    try:
        if IS_WIN:
            import ctypes

            class MS(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
            s = MS()
            s.dwLength = ctypes.sizeof(MS)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(s))
            return s.ullTotalPhys / 2**30
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    return int(line.split()[1]) / 2**20
    except Exception:
        pass
    return 8.0


def gpu_devices(server_bin):
    """GPUs llama.cpp can use: [{name, vram_mib, free_mib}] (Vulkan on ASKus, CUDA/Vulkan on
    Windows). Empty list = CPU only."""
    if not server_bin:
        return []
    try:
        r = subprocess.run([server_bin, "--list-devices"], capture_output=True, text=True, timeout=60,
                           **_no_window())
    except (OSError, subprocess.TimeoutExpired):
        return []
    devs = []
    for line in (r.stdout + r.stderr).splitlines():
        m = re.match(r"\s*((?:CUDA|Vulkan|ROCm|SYCL|Metal)\d+):\s*(.+?)\s*\((\d+)\s*MiB,\s*(\d+)\s*MiB free\)", line)
        if m:
            devs.append({"id": m.group(1), "name": m.group(2), "vram_mib": int(m.group(3)),
                         "free_mib": int(m.group(4))})
    return devs


def pick_model(models_status, registry, ram, gpus):
    """Largest verified model this computer can run comfortably; else the smallest verified."""
    vram = max((g["vram_mib"] for g in gpus), default=0) / 1024
    ok = [s for s in models_status if s["verified"]]
    if not ok:
        return None
    reg = {m["id"]: m for m in registry}
    fitting = [s for s in ok if ram >= reg[s["id"]]["min_ram_gb"] and
               (reg[s["id"]]["min_vram_gb"] == 0 or vram >= reg[s["id"]]["min_vram_gb"])]
    pool = fitting or ok
    return max(pool, key=lambda s: reg[s["id"]]["approx_gb"])["id"] if fitting else \
        min(pool, key=lambda s: reg[s["id"]]["approx_gb"])["id"]


def _no_window():
    return {"creationflags": 0x08000000} if IS_WIN else {}   # CREATE_NO_WINDOW


# ---------------------------------------------------------------- engine
class Engine:
    """Runs llama-server on 127.0.0.1 with a random port and a random API key. In ASKus it
    runs inside the same no-network sandbox as the app, so nothing else can reach it."""

    def __init__(self, paths):
        self.paths = paths
        self.proc = None
        self.port = 0
        self.key = secrets.token_hex(16)
        self.model_id = None
        self.info = ""
        self.lock = threading.Lock()
        self.log_path = os.path.join(paths.data, ".engine.log") if not IS_WIN else os.path.join(paths.data, "engine.log")

    def _free_port(self):
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        p = s.getsockname()[1]
        s.close()
        return p

    def _help_text(self, binp):
        try:
            return subprocess.run([binp, "--help"], capture_output=True, text=True, timeout=30,
                                  **_no_window()).stdout
        except Exception:
            return ""

    def start(self, model, gpus):
        """model: registry entry (already verified)."""
        with self.lock:
            self.stop_locked()
            binp = self.paths.server_bin
            if not binp:
                raise RuntimeError("The AI engine (llama-server) is not installed.")
            path = os.path.join(self.paths.models, model["file"])
            size_mib = os.path.getsize(path) / 2**20
            ngl = 0
            if gpus:
                free = max(g["free_mib"] for g in gpus) - 1200          # leave room for the context
                per_layer = size_mib / (model["layers"] + 1)
                ngl = max(0, min(model["layers"] + 1, int(free / per_layer)))
            self.port = self._free_port()
            args = [binp, "--host", "127.0.0.1", "--port", str(self.port), "--model", path,
                    "--api-key", self.key, "--ctx-size", "8192", "--n-gpu-layers", str(ngl),
                    "--jinja", "--alias", model["id"]]
            help_text = self._help_text(binp)
            if "--no-webui" in help_text:
                args.append("--no-webui")
            log = open(self.log_path, "w", encoding="utf-8", errors="replace")
            self.proc = subprocess.Popen(args, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                         **_no_window())
            self.model_id = model["id"]
            where = f"{ngl} of {model['layers'] + 1} layers on GPU" if ngl else "CPU"
            self.info = f"{model['name']} · {where}"
            # wait until the model is loaded
            deadline = time.time() + 600
            while time.time() < deadline:
                if self.proc.poll() is not None:
                    raise RuntimeError("The AI engine stopped while loading. See engine log: " + self.log_path)
                try:
                    req = urllib.request.Request(f"http://127.0.0.1:{self.port}/health",
                                                 headers={"Authorization": "Bearer " + self.key})
                    with _opener().open(req, timeout=3) as r:
                        if r.status == 200:
                            return self.info
                except Exception:
                    pass
                time.sleep(0.5)
            raise RuntimeError("The AI engine took too long to load the model.")

    def stop_locked(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.proc = None
        self.model_id = None

    def stop(self):
        with self.lock:
            self.stop_locked()

    def running(self):
        return self.proc is not None and self.proc.poll() is None

    def stream_chat(self, messages, temperature=0.7):
        """Yields text pieces of the reply (OpenAI-compatible streaming API of llama-server)."""
        body = json.dumps({"model": self.model_id, "messages": messages, "stream": True,
                           "temperature": temperature, "top_p": 0.8 if temperature < 0.65 else 0.95}).encode()
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/v1/chat/completions", data=body,
                                     headers={"Content-Type": "application/json",
                                              "Authorization": "Bearer " + self.key})
        with _opener().open(req, timeout=600) as r:
            for raw in r:
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    delta = json.loads(data)["choices"][0].get("delta", {})
                except (ValueError, KeyError, IndexError):
                    continue
                piece = delta.get("content") or ""
                if piece:
                    yield piece


def _opener():
    # Never use a system proxy for talking to our own engine on 127.0.0.1
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


# ---------------------------------------------------------------- knowledge (RAG)
WORD = re.compile(r"[A-Za-z0-9À-ÿ]{2,}")


def _words(text):
    return [w.lower() for w in WORD.findall(text)]


def read_document(path):
    """Plain text of a .txt/.md/.csv/.pdf file ('' if it can't be read)."""
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext in (".txt", ".md", ".markdown", ".csv", ".log", ".json", ".html", ".htm"):
            with open(path, encoding="utf-8", errors="replace") as f:
                return f.read(5_000_000)
        if ext == ".pdf":
            tool = shutil.which("pdftotext")
            if tool:
                r = subprocess.run([tool, "-layout", "-enc", "UTF-8", path, "-"], capture_output=True,
                                   timeout=120, **_no_window())
                if r.returncode == 0:
                    return r.stdout.decode("utf-8", "replace")
            try:
                from pypdf import PdfReader   # Windows test version
                return "\n".join((p.extract_text() or "") for p in PdfReader(path).pages)
            except Exception:
                return ""
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return ""


class Knowledge:
    """BM25 search over the files in the Knowledge folder. Nothing is trained; the best
    matching passages are handed to the model together with your question."""

    EXTS = (".txt", ".md", ".markdown", ".csv", ".pdf", ".log", ".json", ".html", ".htm")

    def __init__(self, folder):
        self.folder = folder
        self.chunks = []          # (source, text, words)
        self.df = {}
        self.avgdl = 1.0
        self.files = 0
        self.skipped = []
        self.lock = threading.Lock()

    def rebuild(self):
        chunks, skipped, files = [], [], 0
        for root, _d, names in os.walk(self.folder):
            for n in sorted(names):
                if not n.lower().endswith(self.EXTS) or n.startswith("."):
                    continue
                p = os.path.join(root, n)
                text = read_document(p)
                if not text.strip():
                    skipped.append(n)
                    continue
                files += 1
                rel = os.path.relpath(p, self.folder)
                paras = re.split(r"\n\s*\n", text)
                buf = ""
                for para in paras:
                    para = para.strip()
                    if not para:
                        continue
                    if len(buf) + len(para) > 1200 and buf:
                        chunks.append((rel, buf))
                        buf = buf[-200:] + "\n" + para       # small overlap
                    else:
                        buf = (buf + "\n" + para) if buf else para
                    while len(buf) > 2400:
                        chunks.append((rel, buf[:1200]))
                        buf = buf[1000:]
                if buf:
                    chunks.append((rel, buf))
        indexed = [(s, t, _words(t)) for s, t in chunks]
        df = {}
        for _s, _t, ws in indexed:
            for w in set(ws):
                df[w] = df.get(w, 0) + 1
        with self.lock:
            self.chunks = indexed
            self.df = df
            self.avgdl = (sum(len(w) for _s, _t, w in indexed) / len(indexed)) if indexed else 1.0
            self.files = files
            self.skipped = skipped
        return files, len(indexed), skipped

    def search(self, query, k=4, k1=1.4, b=0.75):
        q = set(_words(query))
        with self.lock:
            n = len(self.chunks)
            if not n or not q:
                return []
            scored = []
            for src, text, ws in self.chunks:
                tf = {}
                for w in ws:
                    if w in q:
                        tf[w] = tf.get(w, 0) + 1
                if not tf:
                    continue
                s = 0.0
                for w, f in tf.items():
                    idf = math.log(1 + (n - self.df[w] + 0.5) / (self.df[w] + 0.5))
                    s += idf * f * (k1 + 1) / (f + k1 * (1 - b + b * len(ws) / self.avgdl))
                scored.append((s, src, text))
        scored.sort(reverse=True)
        if not scored:
            return []
        top = scored[0][0]
        return [(src, text) for s, src, text in scored[:k] if s >= top * 0.35 and s > 1.0]


# ---------------------------------------------------------------- chats + feedback
SYSTEM = ("You are ASKus AI, a private assistant running entirely on this computer, with no "
          "internet access. Be accurate and concise. If you are not sure, say so. "
          "When notes from the user's Knowledge folder are provided, use them and cite them as [1], [2].")


class Chat:
    """One conversation, kept in memory only until the user saves it."""

    def __init__(self):
        self.messages = []        # [{"role", "content"}] - what the model sees (without system)
        self.started = time.strftime("%Y-%m-%d %H:%M")

    def title(self):
        first = next((m["content"] for m in self.messages if m["role"] == "user"), "Chat")
        t = re.sub(r"\s+", " ", first).strip()
        return (t[:60] + "…") if len(t) > 60 else t


def build_messages(chat, question, notes, think):
    sys_text = SYSTEM
    if notes:
        sys_text += "\n\nNotes from the Knowledge folder:\n" + "\n\n".join(
            f"[{i}] ({src})\n{text}" for i, (src, text) in enumerate(notes, 1))
    sys_text += "\n" + ("/think" if think else "/no_think")
    return [{"role": "system", "content": sys_text}] + chat.messages + [{"role": "user", "content": question}]


THINK = re.compile(r"<think>.*?</think>\s*", re.S)


def strip_thinking(text):
    return THINK.sub("", text).lstrip()


def save_chat(chat, folder):
    safe = re.sub(r'[\\/:*?"<>|\n\r\t]+', " ", chat.title())[:50].strip() or "Chat"
    name = time.strftime("%Y-%m-%d %H%M ") + safe + ".md"
    path = os.path.join(folder, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# {chat.title()}\n\n_Started {chat.started} · ASKus AI_\n\n")
        for m in chat.messages:
            f.write(("**You:** " if m["role"] == "user" else "**ASKus AI:** ") + m["content"] + "\n\n")
    return path


def log_feedback(folder, model_id, context, answer, rating, correction=""):
    """Thumbs up/down and corrections, one JSON object per line, for fine-tuning later
    (on your own computer only)."""
    entry = {"time": time.strftime("%Y-%m-%dT%H:%M:%S"), "model": model_id, "rating": rating,
             "context": context[-8:], "answer": answer, "correction": correction}
    with open(os.path.join(folder, "feedback.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
