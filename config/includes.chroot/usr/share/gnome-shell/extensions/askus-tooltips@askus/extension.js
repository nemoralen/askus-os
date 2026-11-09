// ASKus OS: show a button's name when you hover over it in the top-right menu
// (Power Off, Lock Screen, Settings, Take Screenshot, the arrows next to Wi-Fi/Bluetooth...).
import St from 'gi://St';
import GLib from 'gi://GLib';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

export default class AskusTooltips extends Extension {
    enable() {
        this._label = new St.Label({style_class: 'askus-tooltip', visible: false, reactive: false});
        Main.uiGroup.add_child(this._label);
        this._hooked = new Map();   // button -> [signal ids]
        this._timer = 0;
        const menu = Main.panel.statusArea.quickSettings.menu;
        this._menu = menu;
        this._menuId = menu.connect('open-state-changed', (_m, open) => {
            if (open)
                this._scan(menu.actor ?? menu.box);
            else
                this._hide();
        });
    }

    _nameOf(btn) {
        let name = btn.accessible_name || '';
        if (!name && btn.get_child && btn.get_child() instanceof St.Label)
            name = btn.get_child().text || '';
        return name;
    }

    _scan(actor) {
        if (!actor)
            return;
        for (const child of actor.get_children()) {
            if (child instanceof St.Button && !this._hooked.has(child) && this._nameOf(child)) {
                const ids = [
                    child.connect('notify::hover', () => (child.hover ? this._showSoon(child) : this._hide())),
                    child.connect('destroy', () => this._hooked.delete(child)),
                ];
                this._hooked.set(child, ids);
            }
            this._scan(child);
        }
    }

    _showSoon(btn) {
        this._clearTimer();
        this._timer = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 350, () => {
            this._timer = 0;
            if (btn.hover)
                this._show(btn);
            return GLib.SOURCE_REMOVE;
        });
    }

    _show(btn) {
        const name = this._nameOf(btn);
        if (!name || !this._label)
            return;
        this._label.text = name;
        const [, lw] = this._label.get_preferred_width(-1);
        const [, lh] = this._label.get_preferred_height(lw);
        const [x, y] = btn.get_transformed_position();
        const [w, h] = btn.get_transformed_size();
        let lx = Math.round(x + w / 2 - lw / 2);
        let ly = Math.round(y + h + 6);
        const mon = Main.layoutManager.findMonitorForActor(btn);
        if (mon) {
            lx = Math.max(mon.x + 4, Math.min(lx, mon.x + mon.width - lw - 4));
            if (ly + lh > mon.y + mon.height)
                ly = Math.round(y - lh - 6);
        }
        this._label.set_position(lx, ly);
        Main.uiGroup.set_child_above_sibling(this._label, null);
        this._label.show();
    }

    _clearTimer() {
        if (this._timer) {
            GLib.source_remove(this._timer);
            this._timer = 0;
        }
    }

    _hide() {
        this._clearTimer();
        this._label?.hide();
    }

    disable() {
        this._clearTimer();
        if (this._menuId)
            this._menu.disconnect(this._menuId);
        this._menuId = 0;
        for (const [btn, ids] of this._hooked) {
            for (const id of ids) {
                try { btn.disconnect(id); } catch (_e) {}
            }
        }
        this._hooked.clear();
        this._label?.destroy();
        this._label = null;
    }
}
