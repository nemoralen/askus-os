// ASKus OS touchpad gestures.
//   3 fingers right / left -> Back / Forward in the app you're using (sends Alt+Left / Alt+Right,
//                             which Files, Tor Browser, Brave, Settings and most apps understand)
//   3 fingers up           -> overview (GNOME, unchanged)
//   4 fingers down         -> minimize the focused window (windows behind it stay as they are)
//   4 fingers up           -> bring back the last window minimized this way (repeat for older
//                             ones); if there is none, open the overview
//   4 fingers left / right -> switch desktops (GNOME, which accepts 3+ fingers)
// Nothing here touches the network: a gesture becomes a key press on this computer only.
import Clutter from 'gi://Clutter';
import Meta from 'gi://Meta';
import Shell from 'gi://Shell';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

const DECIDE = 14;      // px of finger travel before we decide the direction (GNOME's own is 16)
const TRIGGER = 60;     // px of travel needed to act

export default class AskusGestures extends Extension {
    enable() {
        this._stack = [];
        this._reset();
        const seat = Clutter.get_default_backend().get_default_seat();
        this._kbd = seat.create_virtual_device(Clutter.InputDeviceType.KEYBOARD_DEVICE);
        global.stage.connectObject('captured-event::touchpad', this._onEvent.bind(this), this);

        // Our handler must run before GNOME's own 3+ finger handlers ("swipe up = overview",
        // "swipe sideways = switch desktop"). Signal handlers run in the order they were
        // connected, so reconnect GNOME's handlers after ours.
        for (const tracker of [Main.overview._swipeTracker, Main.wm._workspaceAnimation?._swipeTracker]) {
            const g = tracker?._touchpadGesture;
            if (g && typeof g._handleEvent === 'function') {
                global.stage.disconnectObject(g);
                global.stage.connectObject('captured-event::touchpad', g._handleEvent.bind(g), g);
            }
        }
    }

    disable() {
        global.stage.disconnectObject(this);
        this._kbd?.run_dispose();
        this._kbd = null;
        this._stack = [];
    }

    _reset() {
        this._state = 'none';
        this._fingers = 0;
        this._dx = 0;
        this._dy = 0;
    }

    // Which gestures are ours: 3 fingers sideways, 4 fingers up/down.
    _wanted(fingers, horizontal) {
        return (fingers === 3 && horizontal) || (fingers === 4 && !horizontal);
    }

    _onEvent(_actor, event) {
        if (event.type() !== Clutter.EventType.TOUCHPAD_SWIPE)
            return Clutter.EVENT_PROPAGATE;
        const phase = event.get_gesture_phase();
        if (phase === Clutter.TouchpadGesturePhase.BEGIN)
            this._reset();
        const fingers = event.get_touchpad_gesture_finger_count();
        if ((fingers !== 3 && fingers !== 4) ||
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
            const horizontal = Math.abs(this._dx) > Math.abs(this._dy);
            if (!this._wanted(fingers, horizontal)) {   // leave it to GNOME
                this._state = 'ignored';
                return Clutter.EVENT_PROPAGATE;
            }
            this._fingers = fingers;
            this._state = horizontal ? 'sideways' : 'vertical';
        }

        if (phase === Clutter.TouchpadGesturePhase.END) {
            // touchpad deltas follow the fingers: +x = moved right, +y = moved down
            if (this._state === 'sideways') {
                if (this._dx > TRIGGER)
                    this._altKey(Clutter.KEY_Left);      // fingers to the right = Back
                else if (this._dx < -TRIGGER)
                    this._altKey(Clutter.KEY_Right);     // fingers to the left = Forward
            } else if (this._dy > TRIGGER) {
                this._minimize();
            } else if (this._dy < -TRIGGER) {
                this._restore();
            }
            this._reset();
        } else if (phase === Clutter.TouchpadGesturePhase.CANCEL) {
            this._reset();
        }
        return Clutter.EVENT_STOP;
    }

    _altKey(key) {
        if (!this._kbd || !global.display.focus_window)
            return;
        const t = Clutter.get_current_event_time() * 1000;
        this._kbd.notify_keyval(t, Clutter.KEY_Alt_L, Clutter.KeyState.PRESSED);
        this._kbd.notify_keyval(t, key, Clutter.KeyState.PRESSED);
        this._kbd.notify_keyval(t, key, Clutter.KeyState.RELEASED);
        this._kbd.notify_keyval(t, Clutter.KEY_Alt_L, Clutter.KeyState.RELEASED);
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
