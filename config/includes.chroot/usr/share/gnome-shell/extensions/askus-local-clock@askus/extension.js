// ASKus OS: show local time in the top bar. Only this label changes: the system clock,
// every app and Tor stay on UTC, so nothing can reveal your time zone.
// Zone: ~/.config/askus/clock-timezone (set with "Clock Time Zone"), else /etc/askus/clock-timezone.
import GLib from 'gi://GLib';
import Gio from 'gi://Gio';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

const USER_FILE = GLib.build_filenamev([GLib.get_home_dir(), '.config', 'askus', 'clock-timezone']);
const DEFAULT_FILE = '/etc/askus/clock-timezone';

export default class AskusLocalClock extends Extension {
    enable() {
        const dm = Main.panel.statusArea.dateMenu;
        this._label = dm._clockDisplay;
        this._wall = dm._clock;
        this._iface = new Gio.Settings({schema_id: 'org.gnome.desktop.interface'});
        this._tzName = undefined;
        this._tz = null;
        this._readZone();
        this._clockId = this._wall.connect('notify::clock', () => this._update());
        this._ifaceId = this._iface.connect('changed', () => this._update());
        this._timer = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 5, () => {
            if (this._readZone())
                this._update();
            return GLib.SOURCE_CONTINUE;
        });
        this._update();
    }

    _readZone() {
        let name = '';
        for (const f of [USER_FILE, DEFAULT_FILE]) {
            try {
                const [ok, bytes] = GLib.file_get_contents(f);
                if (ok) {
                    name = new TextDecoder().decode(bytes).trim();
                    if (name)
                        break;
                }
            } catch (_e) {}
        }
        if (name === this._tzName)
            return false;
        this._tzName = name;
        this._tz = null;
        if (name && name !== 'UTC' && name !== 'Etc/UTC') {
            try {
                this._tz = GLib.TimeZone.new_identifier(name);
            } catch (_e) {
                this._tz = null;
            }
        }
        return true;
    }

    _update() {
        if (!this._label)
            return;
        if (!this._tz) {
            this._label.text = this._wall.clock;   // UTC, exactly as GNOME shows it
            return;
        }
        const now = GLib.DateTime.new_now(this._tz);
        const h24 = this._iface.get_string('clock-format') === '24h';
        let fmt = '';
        if (this._iface.get_boolean('clock-show-weekday'))
            fmt += '%a ';
        if (this._iface.get_boolean('clock-show-date'))
            fmt += '%b %-d  ';
        fmt += h24 ? '%H:%M' : '%-l:%M %p';
        this._label.text = now.format(fmt).trim();
    }

    disable() {
        if (this._timer)
            GLib.source_remove(this._timer);
        this._timer = 0;
        if (this._clockId)
            this._wall.disconnect(this._clockId);
        if (this._ifaceId)
            this._iface.disconnect(this._ifaceId);
        this._clockId = this._ifaceId = 0;
        if (this._label && this._wall)
            this._label.text = this._wall.clock;
        this._label = this._wall = this._iface = null;
    }
}
