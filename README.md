<h1 align="center">ASKus OS</h1>

A live operating system you boot from a USB stick. It works like **Tails**: everything goes through **Tor**, nothing is written to the computer, and the system forgets everything when you shut down, except what you choose to keep in an **encrypted Persistent Storage**. The desktop is styled after **macOS** and tuned to feel fast.

Built on **Debian 13 "trixie"** with Debian `live-build`. The open-source parts come from Debian and GitHub (WhiteSur theme by vinceliuice), and Tor Browser comes from the Tor Project.

---

## What's inside

| Area | What you get |
|---|---|
| **Anonymity** | System Tor with a fail-closed `nftables` firewall: every TCP connection and DNS lookup is forced through Tor, and everything else (UDP, IPv6, LAN) is blocked · Tor Browser (official build, signature-checked at build time) · bridges (obfs4 / Snowflake / meek) · `torsocks`, `nyx` |
| **Amnesia** | Runs entirely in RAM · freed memory is wiped (`init_on_free=1`) · no swap on disk · powers off at once if the USB stick is pulled out · random MAC address on every connection · no hostname sent over DHCP · UTC clock |
| **Bitcoin** | **Electrum** wallet, preset to connect through Tor |
| **Encryption** | **GnuPG** with **Kleopatra** and Seahorse (public/private keys) · **KeePassXC** · LUKS2 encrypted volumes (GNOME Disks) · zuluCrypt (opens VeraCrypt volumes) · `paperkey` |
| **Metadata & files** | MAT2 / Metadata Cleaner · secure-delete · QR tools |
| **Apps** | Thunderbird · LibreOffice · GIMP · Inkscape · Audacity |
| **Look & feel** | GNOME with the WhiteSur (macOS-style) theme, icons and cursors · Dash-to-Dock at the bottom · close/minimize/maximize buttons on the left · Inter font · natural scrolling · blur effects · ASKus wallpaper, boot splash and logo |
| **Speed** | zstd-compressed system image · zram compressed RAM swap · file indexing and background timers turned off · optional `toram` mode (copies the whole OS into RAM) |

### The Welcome screen (your "Tails Greeter")
It opens every time you start. From it you can:
- **Unlock** your Persistent Storage, or **create** one in the free space of the USB stick (LUKS2, Argon2id).
- Watch Tor connect, paste **bridges** if Tor is blocked, and **fix the clock** (Tor won't connect if the clock is wrong).
- Optionally set an **administration password** for this session. It is off by default, the same as in Tails.

When you press **Start ASKus OS**, these settings lock until the next reboot, so no app can change them afterwards.

**What Persistent Storage keeps:** the `~/Persistent` folder, GnuPG keys (`~/.gnupg`), Electrum wallets, KeePassXC settings, SSH keys, Thunderbird, Wi-Fi passwords and Tor bridges.

---

## 1 · Get the ISO (no Linux machine needed)

1. Create a **public** repository on GitHub, e.g. `askus-os`. Public repos get free build minutes.
2. Upload the contents of this folder. Include the hidden `.github` folder, or `git push` it.
3. Open the **Actions** tab, choose **Build ASKus OS ISO**, then **Run workflow**. The build takes about 45–90 minutes.
4. Download **askus-os-iso** from the finished run.
   Tip: push a tag (`git tag v1.0 && git push --tags`) to publish the ISO as a **Release** as well. A file over 2 GB is split into parts. Join them with `cat askus-os*.part* > askus-os.iso` (on Windows: `copy /b part00+part01 askus-os.iso`).

**Building locally instead** (Debian 13, or a Debian 13 VM):
```bash
sudo ./build.sh
```

## 2 · Put it on a USB stick (8 GB or larger)

- **balenaEtcher** (Windows / Mac / Linux): select the ISO, select the stick, then Flash.
- **Rufus**: when asked, choose **DD Image mode**. *ISO mode breaks Persistent Storage.*
- Linux: `sudo dd if=askus-os-amd64.hybrid.iso of=/dev/sdX bs=4M status=progress oflag=sync`

## 3 · Boot it

| Computer | How |
|---|---|
| Most Windows/Linux PCs | Restart and press the boot-menu key (**F12**, F11, F9, Esc or F8 depending on the brand), then pick the USB stick. Secure Boot works (Debian's signed shim). |
| Intel Macs | Hold **Option (⌥)** at startup and pick "EFI Boot". On T2 Macs, first allow external boot in *Startup Security Utility*. |
| Apple Silicon Macs (M1–M4), ARM | **Not supported.** These need an ARM build. |

At the boot menu you can press **e** (UEFI) or **Tab** (BIOS) and add `toram` to the end of the `linux` line. The whole OS then loads into RAM: it runs faster and you can unplug the stick. You need about 4 GB of free RAM, and Persistent Storage isn't available in this mode.

---

## Security notes (please read)

ASKus OS copies the main protections of Tails, but **it is not Tails**. Tails has years of professional audits and protections this project doesn't have yet (for example a filtered Tor control port, `onion-grater`, Tor-based time sync, and full memory erasure at shutdown). If your safety depends on staying anonymous, use the real Tails.

- The default user is `askus`. Until you set an admin password, the screen-lock password is `live`.
- Local network access (printers, NAS) is blocked on purpose.
- Captive-portal Wi-Fi (hotels, airports) isn't supported because there is no "unsafe browser".
- No software can protect you from hardware keyloggers or a compromised BIOS/firmware.

## Project layout
```
auto/config                         live-build settings (Debian trixie, boot options, hardening flags)
config/package-lists/               core packages
config/hooks/live/0100-*            optional tools, installed one by one (+ verified Electrum fallback)
config/hooks/live/0200-*            Tor Browser download + GPG signature check
config/hooks/live/0300-*            WhiteSur macOS theme from GitHub
config/hooks/live/0400-*            services, privacy defaults, branding, Plymouth
config/includes.chroot/etc/         torrc, nftables firewall, NetworkManager privacy, sysctl, dconf look
config/includes.chroot/usr/local/   Welcome app + root helpers (persistence, bridges, admin, USB watchdog)
branding/                           logo, wordmarks, wallpaper, boot splash (SVG sources + PNG renders)
.github/workflows/build-iso.yml     builds the ISO on GitHub
```

**Customize it:** add packages to `config/package-lists/*.list.chroot`, change the desktop defaults in `config/includes.chroot/etc/dconf/db/local.d/00-askus`, and the logo is generated by `branding/src/` (or drop your own `branding/logo.svg` in place) — every icon, wordmark, wallpaper and boot splash is re-rendered from it automatically during the build (`branding/render.sh`).

## Credits & licenses
Debian, the Tor Project (Tor, Tor Browser), Electrum, GnuPG/KDE (Kleopatra), KeePassXC, MAT2 and GNOME are covered by their own free-software licenses. The WhiteSur GTK theme, icons and cursors are © vinceliuice (GPL-3.0). ASKus OS scripts and configuration are GPL-3.0-or-later. The ASKus OS name and logo are © ASK Us Design & Consulting. ASKus OS is not affiliated with Apple, Tails or the Tor Project.
