"""ASKus Assistant back end: talks to Claude (Anthropic API) and to a local Ollama.

No GTK here, so it can be tested on its own. Everything runs inside the
assistant's sandbox; network traffic goes through Tor via the system firewall.
"""
import base64
import hashlib
import json
import mimetypes
import os
import re
import shutil
import subprocess
import tarfile
import time
import urllib.error
import urllib.request

HOME = os.path.expanduser("~")
CONFIG = os.path.join(HOME, ".config", "askus-assistant", "config.json")
SHARED = os.path.join(HOME, "Shared")
OLLAMA_DIR = os.path.join(HOME, "local-ai")
OLLAMA_BIN = os.path.join(OLLAMA_DIR, "bin", "ollama")
OLLAMA_MODELS = os.path.join(OLLAMA_DIR, "models")
OLLAMA_HOST = "127.0.0.1:11435"

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
CLAUDE_MODELS = [
    ("claude-sonnet-5-5", "Claude Sonnet 5.5 (fast, recommended)"),
    ("claude-opus-5-5", "Claude Opus 5.5 (most capable)"),
    ("claude-haiku-5-5", "Claude Haiku 5.5 (quickest, cheapest)"),
]
LOCAL_MODELS = [
    ("llama3.2:3b", "Llama 3.2 3B (about 2 GB, runs on most PCs)"),
    ("qwen2.5:7b", "Qwen 2.5 7B (about 5 GB, smarter, needs 16 GB RAM)"),
]
SYSTEM_PROMPT = ("You are ASKus Assistant, a helpful assistant built into ASKus OS, a privacy-focused "
                 "Linux system. Be clear and concise.")
MAX_FILE = 20 * 1024 * 1024
TEXT_LIMIT = 400_000
UA = "askus-assistant"


class AssistantError(Exception):
    pass


# ------------------------------------------------------------------ settings
def load_config():
    try:
        with open(CONFIG) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_config(cfg):
    os.makedirs(os.path.dirname(CONFIG), exist_ok=True)
    tmp = CONFIG + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(cfg, f)
    os.replace(tmp, CONFIG)


# ------------------------------------------------------------------ files
def file_blocks(path, for_claude=True):
    """Turn an attached file into message content blocks."""
    name = os.path.basename(path)
    size = os.path.getsize(path)
    if size > MAX_FILE:
        raise AssistantError(f"{name} is larger than 20 MB")
    mime = mimetypes.guess_type(path)[0] or ""
    with open(path, "rb") as f:
        data = f.read()
    if mime in ("image/png", "image/jpeg", "image/gif", "image/webp"):
        if not for_claude:
            return [{"type": "image_b64", "data": base64.b64encode(data).decode()}]
        return [{"type": "image", "source": {"type": "base64", "media_type": mime,
                                             "data": base64.b64encode(data).decode()}}]
    if mime == "application/pdf":
        if not for_claude:
            raise AssistantError("Local AI can't read PDFs yet; use Claude or paste the text")
        return [{"type": "document", "source": {"type": "base64", "media_type": "application/pdf",
                                                "data": base64.b64encode(data).decode()},
                 "title": name}]
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise AssistantError(f"{name} isn't a text, image or PDF file") from None
    if len(text) > TEXT_LIMIT:
        text = text[:TEXT_LIMIT] + "\n…(truncated)"
    return [{"type": "text", "text": f"File: {name}\n```\n{text}\n```"}]


# ------------------------------------------------------------------ Claude
def claude_stream(api_key, model, messages, on_text, stop_flag=None):
    """Send `messages` to Claude and call on_text(chunk) for each piece of the reply."""
    if not api_key:
        raise AssistantError("Add your Claude API key in Settings first")
    body = json.dumps({"model": model, "max_tokens": 8192, "stream": True,
                       "system": SYSTEM_PROMPT, "messages": messages}).encode()
    req = urllib.request.Request(ANTHROPIC_URL, data=body, method="POST", headers={
        "x-api-key": api_key, "anthropic-version": ANTHROPIC_VERSION,
        "content-type": "application/json", "user-agent": UA})
    try:
        resp = urllib.request.urlopen(req, timeout=180)
    except urllib.error.HTTPError as e:
        raise AssistantError(_api_error(e)) from None
    except urllib.error.URLError as e:
        raise AssistantError(f"Can't reach Claude through Tor ({e.reason}). Is Tor connected?") from None
    full = []
    with resp:
        for raw in resp:
            if stop_flag and stop_flag():
                break
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            try:
                ev = json.loads(line[5:].strip())
            except ValueError:
                continue
            if ev.get("type") == "content_block_delta" and ev.get("delta", {}).get("type") == "text_delta":
                chunk = ev["delta"].get("text", "")
                full.append(chunk)
                on_text(chunk)
            elif ev.get("type") == "error":
                raise AssistantError(ev.get("error", {}).get("message", "Claude returned an error"))
    return "".join(full)


def _api_error(e):
    try:
        msg = json.loads(e.read().decode()).get("error", {}).get("message", "")
    except Exception:  # noqa: BLE001
        msg = ""
    if e.code == 401:
        return "Your Claude API key was rejected. Check it in Settings."
    if e.code == 429:
        return "Claude is rate-limiting this key right now. Wait a minute and try again."
    if e.code == 529:
        return "Claude is overloaded right now. Try again shortly."
    return f"Claude error {e.code}: {msg or e.reason}"


# ------------------------------------------------------------------ Local AI (Ollama)
def local_installed():
    return os.path.exists(OLLAMA_BIN)


def _get(url, timeout=60):
    req = urllib.request.Request(url, headers={"user-agent": UA})
    return urllib.request.urlopen(req, timeout=timeout)


def install_local_ai(progress):
    """Download Ollama from its official GitHub release and verify its SHA-256."""
    progress("Finding the latest Ollama release…", 0.01)
    rel = json.load(_get("https://api.github.com/repos/ollama/ollama/releases/latest"))
    assets = {a["name"]: a for a in rel.get("assets", [])}
    pkg = next((assets[n] for n in assets if re.fullmatch(r"ollama-linux-amd64\.(tgz|tar\.zst)", n)), None)
    if not pkg:
        raise AssistantError("Couldn't find the Linux download in the Ollama release")
    expected = None
    if "sha256sum.txt" in assets:
        for line in _get(assets["sha256sum.txt"]["browser_download_url"]).read().decode().splitlines():
            parts = line.split()
            if len(parts) == 2 and parts[1].lstrip("*./") == pkg["name"]:
                expected = parts[0].lower()
    os.makedirs(OLLAMA_DIR, exist_ok=True)
    dest = os.path.join(OLLAMA_DIR, pkg["name"])
    h = hashlib.sha256()
    total = pkg["size"] or 1
    got = 0
    with _get(pkg["browser_download_url"], timeout=300) as r, open(dest, "wb") as out:
        while True:
            b = r.read(1 << 20)
            if not b:
                break
            out.write(b)
            h.update(b)
            got += len(b)
            progress(f"Downloading Ollama through Tor ({got/1e9:.2f} of {total/1e9:.2f} GB)…", 0.02 + 0.6 * got / total)
    if expected and h.hexdigest() != expected:
        os.remove(dest)
        raise AssistantError("The Ollama download failed its checksum and was deleted. Try again.")
    progress("Unpacking…", 0.64)
    if dest.endswith(".tar.zst"):
        subprocess.run(["tar", "--zstd", "-xf", dest, "-C", OLLAMA_DIR], check=True)
    else:
        with tarfile.open(dest) as t:
            t.extractall(OLLAMA_DIR, filter="data")
    os.remove(dest)
    if not local_installed():
        raise AssistantError("Ollama was unpacked but its program wasn't found")
    os.chmod(OLLAMA_BIN, 0o755)
    progress("Ollama installed", 0.66)


class LocalServer:
    def __init__(self):
        self.proc = None

    def running(self):
        try:
            _get(f"http://{OLLAMA_HOST}/api/version", timeout=2).read()
            return True
        except Exception:  # noqa: BLE001
            return False

    def start(self):
        if self.running():
            return
        if not local_installed():
            raise AssistantError("Local AI isn't installed yet (Settings ▸ Install local AI)")
        os.makedirs(OLLAMA_MODELS, exist_ok=True)
        env = dict(os.environ, OLLAMA_HOST=OLLAMA_HOST, OLLAMA_MODELS=OLLAMA_MODELS,
                   OLLAMA_NOPRUNE="1", HOME=HOME)
        self.proc = subprocess.Popen([OLLAMA_BIN, "serve"], env=env,
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(60):
            if self.running():
                return
            time.sleep(0.5)
        raise AssistantError("The local AI engine didn't start")

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()

    def has_model(self, model):
        try:
            tags = json.load(_get(f"http://{OLLAMA_HOST}/api/tags", timeout=5))
        except Exception:  # noqa: BLE001
            return False
        names = {m.get("name") for m in tags.get("models", [])}
        return model in names or f"{model}:latest" in names

    def pull(self, model, progress):
        self.start()
        req = urllib.request.Request(f"http://{OLLAMA_HOST}/api/pull", method="POST",
                                     data=json.dumps({"model": model, "stream": True}).encode(),
                                     headers={"content-type": "application/json"})
        with urllib.request.urlopen(req, timeout=3600) as r:
            for raw in r:
                try:
                    ev = json.loads(raw)
                except ValueError:
                    continue
                if ev.get("error"):
                    raise AssistantError(f"Model download failed: {ev['error']}")
                tot, done = ev.get("total"), ev.get("completed")
                frac = 0.66 + 0.33 * (done / tot) if tot and done else None
                progress(f"Downloading {model} through Tor: {ev.get('status', '')}", frac)
        progress(f"{model} is ready", 1.0)

    def chat_stream(self, model, messages, on_text, stop_flag=None):
        self.start()
        if not self.has_model(model):
            raise AssistantError(f"The model {model} isn't downloaded yet (Settings ▸ Local AI)")
        req = urllib.request.Request(f"http://{OLLAMA_HOST}/api/chat", method="POST",
                                     data=json.dumps({"model": model, "messages": messages,
                                                      "stream": True}).encode(),
                                     headers={"content-type": "application/json"})
        full = []
        with urllib.request.urlopen(req, timeout=600) as r:
            for raw in r:
                if stop_flag and stop_flag():
                    break
                try:
                    ev = json.loads(raw)
                except ValueError:
                    continue
                if ev.get("error"):
                    raise AssistantError(ev["error"])
                chunk = ev.get("message", {}).get("content", "")
                if chunk:
                    full.append(chunk)
                    on_text(chunk)
                if ev.get("done"):
                    break
        return "".join(full)


def to_ollama(messages):
    """Convert Claude-style messages (content blocks) to Ollama chat messages."""
    out = [{"role": "system", "content": SYSTEM_PROMPT}]
    for m in messages:
        if isinstance(m["content"], str):
            out.append({"role": m["role"], "content": m["content"]})
            continue
        texts, images = [], []
        for b in m["content"]:
            if b["type"] == "text":
                texts.append(b["text"])
            elif b["type"] == "image_b64":
                images.append(b["data"])
        msg = {"role": m["role"], "content": "\n\n".join(texts)}
        if images:
            msg["images"] = images
        out.append(msg)
    return out


def disk_free_gb(path=HOME):
    return shutil.disk_usage(path).free / 1e9
