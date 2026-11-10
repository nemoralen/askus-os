// ASKus OS: 4-finger touchpad swipes.
//   swipe down -> minimize the focused window (windows behind it stay as they are)
//   swipe up   -> bring back the last window minimized this way (repeat for older ones);
//                 if there is none, open the overview
// 3-finger gestures (overview, switching workspaces) keep working as before.
import Clutter from 'gi://Clutter';
import Meta from 'gi://Meta';
import Shell from 'gi://Shell';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

const FINGERS = 4;
const DECIDE = 14;      // px of finger travel before we decide the direction (GNOME's own is 16)
const TRIGGER = 60;     // px of vertical travel needed to act

export default class AskusGestures extends Extension {
    enable() {
        this._stack = [];
        this._reset();
        global.stage.connectObject('captured-event::touchpad', this._onEvent.bind(this), this);

        // Our handler must run before GNOME's "swipe up = overview" one, which accepts 3+
        // fingers. Signal handlers run in the order they were connected, so reconnect GNOME's
        // handler after ours.
        const g = Main.overview._swipeTracker?._touchpadGesture;
        if (g && typeof g._handleEvent === 'function') {
            global.stage.disconnectObject(g);
            global.stage.connectObject('captured-event::touchpad', g._handleEvent.bind(g), g);
        }
    }

    disable() {
        global.stage.disconnectObject(this);
        this._stack = [];
    }

    _reset() {
        this._state = 'none';
        this._dx = 0;
        this._dy = 0;
    }

    _onEvent(_actor, event) {
        if (event.type() !== Clutter.EventType.TOUCHPAD_SWIPE)
            return Clutter.EVENT_PROPAGATE;
        const phase = event.get_gesture_phase();
        if (phase === Clutter.TouchpadGesturePhase.BEGIN)
            this._reset();
        if (event.get_touchpad_gesture_finger_count() !== FINGERS ||
            Main.actionMode !== Shell.ActionMode.NORMAL || this._state === 'ignored')
            return Clutter.EVENT_PROPAGATE;

        const [dx, dy] = event.get_gesture_motion_delta_unaccelerated();
        this._dx += dx;
        this._dy += dy;

        if (this._state === 'none') {
            if (Math.hypot(this._dx, this._dy) < DECIDE) {
                if (phase === Clutter.TouchpadGesturePhase.END ||
                    phase === Clutter.TouchpadGesturePhase.CANCEL)
                    this._reset();
                return Clutter.EVENT_PROPAGATE;
            }
            if (Math.abs(this._dx) > Math.abs(this._dy)) {   // sideways: leave it to GNOME
                this._state = 'ignored';
                return Clutter.EVENT_PROPAGATE;
            }
            this._state = 'mine';
        }

        if (phase === Clutter.TouchpadGesturePhase.END) {
            // touchpad deltas follow the fingers: positive y = fingers moved down
            if (this._dy > TRIGGER)
                this._minimize();
            else if (this._dy < -TRIGGER)
                this._restore();
            this._reset();
        } else if (phase === Clutter.TouchpadGesturePhase.CANCEL) {
            this._reset();
        }
        return Clutter.EVENT_STOP;
    }

    _minimize() {
        const win = global.display.focus_window;
        if (!win || win.window_type !== Meta.WindowType.NORMAL || !win.can_minimize() ||
            win.skip_taskbar)   // the desktop icons window, panels, etc.
            return;
        this._stack = this._stack.filter(w => w !== win);
        this._stack.push(win);
        win.minimize();
    }

    _restore() {
        while (this._stack.length) {
            const win = this._stack.pop();
            // skip windows that were closed or already brought back some other way
            if (!win.get_compositor_private() || !win.minimized)
                continue;
            win.unminimize();
            win.activate(global.get_current_time());
            return;
        }
        Main.overview.show();
    }
}
