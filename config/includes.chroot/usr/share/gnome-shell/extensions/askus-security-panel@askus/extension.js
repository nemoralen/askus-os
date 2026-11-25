// ASKus OS: shield icon in the top bar. Green = all good, yellow = worth a look,
// red = something is wrong (Tor down, firewall off, system files changed).
// Click it for the details. Data comes from /usr/local/bin/askus-security-status
// (no network use), refreshed every 10 seconds.
import GLib from 'gi://GLib';
import Gio from 'gi://Gio';
import St from 'gi://St';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

const HELPER = '/usr/local/bin/askus-security-status';
const COLORS = {ok: '#4ade80', warn: '#facc15', bad: '#f87171'};
const ICONS = {ok: 'security-high-symbolic', warn: 'security-medium-symbolic', bad: 'security-low-symbolic'};

export default class AskusSecurityPanel extends Extension {
    enable() {
        this._button = new PanelMenu.Button(0.0, 'ASKus Security', false);
        this._icon = new St.Icon({icon_name: ICONS.ok, style_class: 'system-status-icon'});
        this._button.add_child(this._icon);
        this._section = new PopupMenu.PopupMenuSection();
        this._button.menu.addMenuItem(this._section);
        this._button.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());
        const tor = new PopupMenu.PopupMenuItem('Check Tor connection…');
        tor.connect('activate', () => this._spawn(['/usr/local/bin/askus-tor-status']));
        this._button.menu.addMenuItem(tor);
        const leak = new PopupMenu.PopupMenuItem('Run leak test…');
        leak.connect('activate', () => this._spawn(['/usr/local/bin/askus-leak-test']));
        this._button.menu.addMenuItem(leak);
        this._button.menu.connect('open-state-changed', (_m, open) => {
            if (open)
                this._refresh();
        });
        Main.panel.addToStatusArea(this.uuid, this._button, 0, 'right');
        this._cancel = null;
        this._refresh();
        this._timer = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 10, () => {
            this._refresh();
            return GLib.SOURCE_CONTINUE;
        });
    }

    _spawn(argv) {
        try {
            Gio.Subprocess.new(argv, Gio.SubprocessFlags.NONE);
        } catch (e) {
            logError(e, 'askus-security-panel');
        }
    }

    _refresh() {
        if (this._cancel)
            return;   // previous check still running
        let proc;
        try {
            proc = Gio.Subprocess.new([HELPER], Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_SILENCE);
        } catch (e) {
            this._show({level: 'warn', items: [{name: 'Status', value: 'not available', level: 'warn'}]});
            return;
        }
        this._cancel = new Gio.Cancellable();
        proc.communicate_utf8_async(null, this._cancel, (p, res) => {
            this._cancel = null;
            if (!this._button)
                return;
            try {
                const [, out] = p.communicate_utf8_finish(res);
                this._show(JSON.parse(out));
            } catch (_e) {
                this._show({level: 'warn', items: [{name: 'Status', value: 'not available', level: 'warn'}]});
            }
        });
    }

    _show(data) {
        const level = data.level in ICONS ? data.level : 'warn';
        this._icon.icon_name = ICONS[level];
        this._icon.style = `color: ${COLORS[level]};`;
        this._section.removeAll();
        for (const it of data.items || []) {
            const item = new PopupMenu.PopupMenuItem('', {reactive: false});
            const dot = new St.Label({text: '●  ', style: `color: ${COLORS[it.level] || COLORS.warn};`});
            item.insert_child_at_index(dot, 0);
            item.label.text = `${it.name}:  ${it.value}`;
            this._section.addMenuItem(item);
        }
    }

    disable() {
        if (this._timer)
            GLib.source_remove(this._timer);
        this._timer = 0;
        if (this._cancel)
            this._cancel.cancel();
        this._cancel = null;
        this._button?.destroy();
        this._button = null;
        this._icon = null;
        this._section = null;
    }
}
