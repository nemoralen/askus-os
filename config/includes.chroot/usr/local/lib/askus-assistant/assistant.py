#!/usr/bin/python3
"""ASKus Assistant: chat with Claude (cloud, private but not anonymous) or a Local AI
(offline). Runs inside a firejail sandbox started by /usr/local/bin/askus-assistant.
It can only see files you put in the "Shared with AI" folder."""
import os
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import backend as be  # noqa: E402

import gi  # noqa: E402
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk  # noqa: E402

CSS = b"""
.mode-claude headerbar { background: linear-gradient(90deg, #4C1D95, #7C3AED); color: white; }
.mode-local  headerbar { background: linear-gradient(90deg, #064E3B, #059669); color: white; }
.mode-claude { border: 3px solid #7C3AED; }
.mode-local  { border: 3px solid #059669; }
.bubble { padding: 10px 14px; border-radius: 14px; }
.bubble-user { background: alpha(@accent_bg_color, 0.25); }
.bubble-ai   { background: alpha(@card_bg_color, 0.9); }
.bubble-err  { background: alpha(#DC2626, 0.25); }
.mode-pill { font-size: 9pt; font-weight: 700; padding: 2px 10px; border-radius: 99px;
             background: alpha(white, 0.18); }
.attach-chip { font-size: 9pt; padding: 2px 8px; border-radius: 99px; background: alpha(@accent_bg_color, 0.2); }
"""


class Window(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="ASKus Assistant")
        self.set_default_size(760, 820)
        self.cfg = be.load_config()
        self.mode = self.cfg.get("mode", "claude")
        self.history = []          # messages in Claude format
        self.attachments = []
        self.busy = False
        self.stop_requested = False
        self.warned_claude = False
        self.local = be.LocalServer()
        self.connect("close-request", lambda *_: (self.local.stop(), False)[1])

        self.toasts = Adw.ToastOverlay()
        view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.title_lbl = Gtk.Label(label="ASKus Assistant")
        self.title_lbl.add_css_class("title")
        self.pill = Gtk.Label()
        self.pill.add_css_class("mode-pill")
        box.append(self.title_lbl)
        box.append(self.pill)
        header.set_title_widget(box)

        seg = Gtk.Box(css_classes=["linked"])
        self.btn_claude = Gtk.ToggleButton(label="Claude")
        self.btn_local = Gtk.ToggleButton(label="Local AI", group=self.btn_claude)
        self.btn_claude.connect("toggled", self.on_mode_toggle)
        seg.append(self.btn_claude)
        seg.append(self.btn_local)
        header.pack_start(seg)

        menu = Gio.Menu()
        menu.append("Settings", "win.settings")
        menu.append("New conversation", "win.clear")
        menu.append("Open “Shared with AI” folder", "win.shared")
        header.pack_end(Gtk.MenuButton(icon_name="open-menu-symbolic", menu_model=menu))
        for name, cb in (("settings", self.open_settings), ("clear", lambda *_: self.clear(True)),
                         ("shared", self.open_shared)):
            act = Gio.SimpleAction.new(name, None)
            act.connect("activate", cb)
            self.add_action(act)
        view.add_top_bar(header)

        # conversation
        self.msgs = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10,
                            margin_top=14, margin_bottom=14, margin_start=14, margin_end=14)
        self.scroller = Gtk.ScrolledWindow(vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER)
        clamp = Adw.Clamp(maximum_size=760)
        clamp.set_child(self.msgs)
        self.scroller.set_child(clamp)

        # input area
        bottom = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6,
                         margin_start=12, margin_end=12, margin_bottom=12)
        self.chips = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, max_children_per_line=6)
        bottom.append(self.chips)
        row = Gtk.Box(spacing=8)
        attach = Gtk.Button(icon_name="mail-attachment-symbolic", valign=Gtk.Align.END,
                            tooltip_text="Attach a file from “Shared with AI”")
        attach.connect("clicked", self.on_attach)
        self.input = Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD_CHAR, top_margin=8, bottom_margin=8,
                                  left_margin=10, right_margin=10, accepts_tab=False)
        key = Gtk.EventControllerKey()
        key.connect("key-pressed", self.on_key)
        self.input.add_controller(key)
        frame = Gtk.Frame(hexpand=True)
        sc = Gtk.ScrolledWindow(min_content_height=60, max_content_height=200, propagate_natural_height=True)
        sc.set_child(self.input)
        frame.set_child(sc)
        self.send_btn = Gtk.Button(icon_name="go-up-symbolic", valign=Gtk.Align.END, tooltip_text="Send (Ctrl+Enter)")
        self.send_btn.add_css_class("suggested-action")
        self.send_btn.add_css_class("circular")
        self.send_btn.connect("clicked", self.on_send)
        row.append(attach)
        row.append(frame)
        row.append(self.send_btn)
        bottom.append(row)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        content.append(self.scroller)
        content.append(bottom)
        view.set_content(content)
        self.toasts.set_child(view)
        self.set_content(self.toasts)

        (self.btn_claude if self.mode == "claude" else self.btn_local).set_active(True)
        self.apply_mode()
        self.welcome()

    # ------------------------------------------------------------ helpers
    def toast(self, t):
        self.toasts.add_toast(Adw.Toast(title=t, timeout=5))

    def bubble(self, text, who):
        lbl = Gtk.Label(label=text, wrap=True, wrap_mode=2, xalign=0, selectable=True,
                        max_width_chars=80)
        lbl.add_css_class("bubble")
        lbl.add_css_class({"user": "bubble-user", "ai": "bubble-ai", "err": "bubble-err"}[who])
        lbl.set_halign(Gtk.Align.END if who == "user" else Gtk.Align.START)
        self.msgs.append(lbl)
        GLib.idle_add(self.scroll_end)
        return lbl

    def scroll_end(self):
        adj = self.scroller.get_vadjustment()
        adj.set_value(adj.get_upper())
        return False

    def welcome(self):
        if self.mode == "claude":
            self.bubble("Claude mode: your messages go to Anthropic through Tor. Anthropic can't see your IP "
                        "address, but your API account identifies you, so this is private, not anonymous.\n\n"
                        "To share a file, put it in the “Shared with AI” folder (in Files) and click 📎.", "ai")
        else:
            self.bubble("Local AI mode: everything stays on this computer. Nothing is sent anywhere.\n\n"
                        + ("" if be.local_installed() else
                           "Local AI isn't installed yet. Open ☰ ▸ Settings ▸ Install local AI."), "ai")

    def apply_mode(self):
        for c in ("mode-claude", "mode-local"):
            self.remove_css_class(c)
        self.add_css_class("mode-" + self.mode)
        if self.mode == "claude":
            model = self.cfg.get("claude_model", be.CLAUDE_MODELS[0][0])
            self.pill.set_label(f"CLAUDE · private, not anonymous · {model}")
        else:
            model = self.cfg.get("local_model", be.LOCAL_MODELS[0][0])
            self.pill.set_label(f"LOCAL AI · offline · {model}")

    def on_mode_toggle(self, btn):
        new = "claude" if self.btn_claude.get_active() else "local"
        if new == self.mode:
            return
        self.mode = new
        self.cfg["mode"] = new
        be.save_config(self.cfg)
        self.clear(False)   # never carry a conversation from one AI to the other
        self.apply_mode()
        self.welcome()

    def clear(self, announce):
        self.history = []
        self.attachments = []
        self.refresh_chips()
        while (c := self.msgs.get_first_child()):
            self.msgs.remove(c)
        if announce:
            self.welcome()

    def open_shared(self, *_):
        os.makedirs(be.SHARED, exist_ok=True)
        Gio.AppInfo.launch_default_for_uri("file://" + be.SHARED, None)

    # ------------------------------------------------------------ attachments
    def on_attach(self, _b):
        os.makedirs(be.SHARED, exist_ok=True)
        dlg = Gtk.FileDialog(title="Attach from “Shared with AI”",
                             initial_folder=Gio.File.new_for_path(be.SHARED))

        def done(d, res):
            try:
                files = d.open_multiple_finish(res)
            except GLib.Error:
                return
            for i in range(files.get_n_items()):
                p = files.get_item(i).get_path()
                if p and os.path.isfile(p):
                    self.attachments.append(p)
            self.refresh_chips()
        dlg.open_multiple(self, None, done)

    def refresh_chips(self):
        while (c := self.chips.get_first_child()):
            self.chips.remove(c)
        for p in self.attachments:
            lbl = Gtk.Label(label="📄 " + os.path.basename(p))
            lbl.add_css_class("attach-chip")
            self.chips.append(lbl)

    # ------------------------------------------------------------ sending
    def on_key(self, _c, keyval, _code, state):
        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter) and state & Gdk.ModifierType.CONTROL_MASK:
            self.on_send(None)
            return True
        return False

    def on_send(self, _b):
        if self.busy:
            self.stop_requested = True
            return
        buf = self.input.get_buffer()
        text = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False).strip()
        if not text and not self.attachments:
            return
        if self.mode == "claude" and not self.warned_claude:
            self.confirm_claude(lambda: self.send(text))
            return
        self.send(text)

    def confirm_claude(self, then):
        dlg = Adw.AlertDialog(
            heading="Send to Claude?",
            body="Your message and any attached files go to Anthropic through Tor. Your IP address stays hidden, "
                 "but your API account identifies you.\n\nDon't paste anything from your anonymous Tor sessions.")
        dlg.add_response("cancel", "Cancel")
        dlg.add_response("send", "Send")
        dlg.set_response_appearance("send", Adw.ResponseAppearance.SUGGESTED)

        def resp(_d, r):
            if r == "send":
                self.warned_claude = True
                then()
        dlg.connect("response", resp)
        dlg.present(self)

    def send(self, text):
        try:
            blocks = []
            for p in self.attachments:
                blocks += be.file_blocks(p, for_claude=(self.mode == "claude"))
        except be.AssistantError as e:
            self.toast(str(e))
            return
        if text:
            blocks.append({"type": "text", "text": text})
        names = ", ".join(os.path.basename(p) for p in self.attachments)
        self.bubble((text or "") + (f"\n📎 {names}" if names else ""), "user")
        self.history.append({"role": "user", "content": blocks})
        self.input.get_buffer().set_text("")
        self.attachments = []
        self.refresh_chips()
        reply = self.bubble("…", "ai")
        self.set_busy(True)
        threading.Thread(target=self.worker, args=(reply,), daemon=True).start()

    def set_busy(self, b):
        self.busy = b
        self.stop_requested = False
        self.send_btn.set_icon_name("media-playback-stop-symbolic" if b else "go-up-symbolic")
        self.send_btn.set_tooltip_text("Stop" if b else "Send (Ctrl+Enter)")

    def worker(self, reply_lbl):
        acc = []

        def on_text(chunk):
            acc.append(chunk)
            GLib.idle_add(reply_lbl.set_label, "".join(acc))
            GLib.idle_add(self.scroll_end)
        try:
            if self.mode == "claude":
                out = be.claude_stream(self.cfg.get("api_key", ""),
                                       self.cfg.get("claude_model", be.CLAUDE_MODELS[0][0]),
                                       self.history, on_text, lambda: self.stop_requested)
            else:
                out = self.local.chat_stream(self.cfg.get("local_model", be.LOCAL_MODELS[0][0]),
                                             be.to_ollama(self.history), on_text, lambda: self.stop_requested)
            self.history.append({"role": "assistant", "content": out or "(stopped)"})
            if not out:
                GLib.idle_add(reply_lbl.set_label, "(stopped)")
        except Exception as e:  # noqa: BLE001
            self.history.pop()      # drop the unanswered question so the conversation stays valid
            GLib.idle_add(reply_lbl.set_label, f"⚠️ {e}")
            GLib.idle_add(lambda: (reply_lbl.remove_css_class("bubble-ai"), reply_lbl.add_css_class("bubble-err")))
        GLib.idle_add(self.set_busy, False)

    # ------------------------------------------------------------ settings
    def open_settings(self, *_):
        dlg = Adw.PreferencesDialog(title="ASKus Assistant settings")
        page = Adw.PreferencesPage()

        g1 = Adw.PreferencesGroup(title="Claude (cloud)",
                                  description="Get an API key at console.anthropic.com. It's stored inside the "
                                              "assistant's sandbox, in Persistent Storage if it's unlocked.")
        key = Adw.PasswordEntryRow(title="API key", show_apply_button=True)
        if self.cfg.get("api_key"):
            key.set_text(self.cfg["api_key"])

        def save_key(row):
            self.cfg["api_key"] = row.get_text().strip()
            be.save_config(self.cfg)
            self.toast("API key saved")
        key.connect("apply", save_key)
        g1.add(key)
        cm = Adw.ComboRow(title="Model", model=Gtk.StringList.new([n for _, n in be.CLAUDE_MODELS]))
        ids = [i for i, _ in be.CLAUDE_MODELS]
        cm.set_selected(ids.index(self.cfg.get("claude_model", ids[0])) if self.cfg.get("claude_model", ids[0]) in ids else 0)
        cm.connect("notify::selected", lambda r, _p: self.set_cfg("claude_model", ids[r.get_selected()]))
        g1.add(cm)
        page.add(g1)

        g2 = Adw.PreferencesGroup(title="Local AI (offline)",
                                  description="Runs entirely on this computer with Ollama. Downloads about 2–7 GB "
                                              "once, through Tor. Unlock Persistent Storage first so it's kept.")
        lids = [i for i, _ in be.LOCAL_MODELS]
        lm = Adw.ComboRow(title="Model", model=Gtk.StringList.new([n for _, n in be.LOCAL_MODELS]))
        cur = self.cfg.get("local_model", lids[0])
        lm.set_selected(lids.index(cur) if cur in lids else 0)
        lm.connect("notify::selected", lambda r, _p: self.set_cfg("local_model", lids[r.get_selected()]))
        g2.add(lm)
        status = Adw.ActionRow(title="Status",
                               subtitle="Installed" if be.local_installed() else "Not installed")
        btn = Gtk.Button(label="Install / download model", valign=Gtk.Align.CENTER)
        btn.add_css_class("suggested-action")
        bar = Gtk.ProgressBar(visible=False, valign=Gtk.Align.CENTER, width_request=140)
        status.add_suffix(bar)
        status.add_suffix(btn)
        g2.add(status)
        page.add(g2)

        def install(_b):
            if be.disk_free_gb() < 9:
                self.toast("Not enough space here. Unlock Persistent Storage (needs about 9 GB free).")
                return
            btn.set_sensitive(False)
            bar.set_visible(True)
            model = self.cfg.get("local_model", lids[0])

            def prog(msg, frac):
                GLib.idle_add(status.set_subtitle, msg)
                if frac is not None:
                    GLib.idle_add(bar.set_fraction, min(1, frac))

            def run():
                try:
                    if not be.local_installed():
                        be.install_local_ai(prog)
                    self.local.pull(model, prog)
                    GLib.idle_add(self.toast, f"Local AI ready: {model}")
                except Exception as e:  # noqa: BLE001
                    GLib.idle_add(status.set_subtitle, f"⚠️ {e}")
                GLib.idle_add(btn.set_sensitive, True)
            threading.Thread(target=run, daemon=True).start()
        btn.connect("clicked", install)

        dlg.add(page)
        dlg.present(self)

    def set_cfg(self, k, v):
        self.cfg[k] = v
        be.save_config(self.cfg)
        self.apply_mode()


class App(Adw.Application):
    def __init__(self):
        super().__init__(application_id="org.askus.Assistant")

    def do_activate(self):
        prov = Gtk.CssProvider()
        prov.load_from_string(CSS.decode())
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), prov,
                                                  Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.PREFER_DARK)
        (self.props.active_window or Window(self)).present()


if __name__ == "__main__":
    sys.exit(App().run(sys.argv))
