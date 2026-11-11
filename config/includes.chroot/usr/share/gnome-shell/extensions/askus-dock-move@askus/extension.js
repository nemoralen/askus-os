// ASKus OS: move the dock by dragging it.
// Press and hold an empty spot on the dock (between/around the icons, not on an icon) for
// half a second, then drag towards the top, left, right or bottom of the screen and let go.
// A highlight shows where the dock will go. Icons keep working as before (click, drag to
// reorder, right-click menu), because presses on icons are never touched.
import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import St from 'gi://St';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

const SCHEMA = 'org.gnome.shell.extensions.dash-to-dock';
const HOLD_MS = 450;
const START_PX = 20;     // how far to drag (after holding) before the move starts
const CANCEL_PX = 8;     // moving this much before the hold is done = normal use, no move
const EDGE = 0.18;       // the highlight covers this share of the screen

export default class AskusDockMove extends Extension {
    enable() {
        const src = Gio.SettingsSchemaSource.get_default();
        if (!src.lookup(SCHEMA, true))
            return;                       // dock extension not installed
        this._dock = new Gio.Settings({schema_id: SCHEMA});
        this._state = 'idle';
        global.stage.connectObject('captured-event', this._onEvent.bind(this), this);
    }

    disable() {
        global.stage.disconnectObject(this);
        this._cancel();
        this._dock = null;
    }

    _inDockBackground(actor) {
        let inDock = false;
        for (let a = actor; a; a = a.get_parent()) {
            if (a instanceof St.Button)
                return false;             // an icon (or Show Apps): leave it alone
            if (a.name === 'dashtodockContainer') {
                inDock = true;
                break;
            }
        }
        return inDock;
    }

    _onEvent(_stage, event) {
        const type = event.type();
        if (this._state === 'idle') {
            if (type === Clutter.EventType.BUTTON_PRESS && event.get_button() === 1 &&
                this._inDockBackground(event.get_source())) {
                [this._x0, this._y0] = event.get_coords();
                this._state = 'armed';
                this._timer = GLib.timeout_add(GLib.PRIORITY_DEFAULT, HOLD_MS, () => {
                    this._timer = 0;
                    if (this._state === 'armed')
                        this._state = 'ready';
                    return GLib.SOURCE_REMOVE;
                });
            }
            return Clutter.EVENT_PROPAGATE;
        }

        const [x, y] = event.get_coords();
        const moved = Math.hypot(x - this._x0, y - this._y0);
        if (type === Clutter.EventType.MOTION) {
            if (this._state === 'armed') {
                if (moved > CANCEL_PX)
                    this._cancel();
                return Clutter.EVENT_PROPAGATE;
            }
            if (this._state === 'ready' && moved > START_PX)
                this._state = 'dragging';
            if (this._state === 'dragging')
                this._showTarget(x, y);
            return Clutter.EVENT_STOP;        // nothing else reacts while we hold the dock
        }
        if (type === Clutter.EventType.BUTTON_RELEASE) {
            const dragging = this._state === 'dragging';
            if (dragging) {
                const pos = this._edgeFor(x, y);
                if (pos && this._dock.get_string('dock-position') !== pos)
                    this._dock.set_string('dock-position', pos);
            }
            this._cancel();
            return dragging ? Clutter.EVENT_STOP : Clutter.EVENT_PROPAGATE;
        }
        return Clutter.EVENT_PROPAGATE;
    }

    _monitorAt(x, y) {
        for (const m of Main.layoutManager.monitors) {
            if (x >= m.x && x < m.x + m.width && y >= m.y && y < m.y + m.height)
                return m;
        }
        return Main.layoutManager.primaryMonitor;
    }

    // Closest edge of the screen the pointer is on, measured relative to its size.
    _edgeFor(x, y) {
        const m = this._monitorAt(x, y);
        if (!m)
            return null;
        const fx = (x - m.x) / m.width, fy = (y - m.y) / m.height;
        const d = {TOP: fy, BOTTOM: 1 - fy, LEFT: fx, RIGHT: 1 - fx};
        return Object.keys(d).reduce((a, b) => (d[a] <= d[b] ? a : b));
    }

    _showTarget(x, y) {
        const m = this._monitorAt(x, y);
        const pos = this._edgeFor(x, y);
        if (!m || !pos)
            return;
        if (!this._box) {
            this._box = new St.Widget({
                style: 'background-color: rgba(120,140,255,0.28); border: 2px solid rgba(160,175,255,0.9); border-radius: 14px;',
                reactive: false,
            });
            Main.layoutManager.uiGroup.add_child(this._box);
        }
        const w = Math.round(m.width * EDGE), h = Math.round(m.height * EDGE);
        const geo = {
            TOP: [m.x, m.y, m.width, h],
            BOTTOM: [m.x, m.y + m.height - h, m.width, h],
            LEFT: [m.x, m.y, w, m.height],
            RIGHT: [m.x + m.width - w, m.y, w, m.height],
        }[pos];
        this._box.set_position(geo[0], geo[1]);
        this._box.set_size(geo[2], geo[3]);
        this._box.show();
        Main.layoutManager.uiGroup.set_child_above_sibling(this._box, null);
    }

    _cancel() {
        if (this._timer) {
            GLib.source_remove(this._timer);
            this._timer = 0;
        }
        this._box?.destroy();
        this._box = null;
        this._state = 'idle';
    }
}
