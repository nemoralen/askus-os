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
| Microsoft Surface (Intel: Pro 3–10, Laptop, Book, Go) | **Turn Secure Boot off first:** shut down, hold **Volume Up** + press **Power**, open *Security → Secure Boot → Disabled*. Then shut down, hold **Volume Down** + press **Power** to boot from USB. ASKus OS detects the Surface and starts the **ASKus OS (Surface)** entry by itself, which adds the [linux-surface](https://github.com/linux-surface/linux-surface) drivers for the keyboard cover, touchpad and touchscreen. With Secure Boot on, the normal entry starts instead (keyboard cover and touch won't work; a USB mouse/keyboard will). |

At the boot menu you can press **e** (UEFI) or **Tab** (BIOS) and add `toram` to the end of the `linux` line. The whole OS then loads into RAM: it runs faster and you can unplug the stick. You need about 4 GB of free RAM, and Persistent Storage isn't available in this mode.

---

---

## Desktop

- **Screen lock:** the Welcome screen asks you to choose a lock password for the session. Until you do, the screen never locks. (If you enable the administration password, the lock screen uses that.)
- **Dock:** open **Dock & Desktop** to put the dock at the bottom, left, right or top, change its size, or turn auto-hide off.
- **Right-click on the desktop:** new folder or document, paste, arrange icons, open in Terminal, change background, display settings.
- **Right-click on files** (**Scripts** menu in Files): *Encrypt with password*, *Decrypt*, *Remove metadata*, *Securely delete*, *Show SHA-256 checksum*. Also *Open in Terminal*, *Compress* and *Extract*.
- **Backgrounds:** five ASKus colour variants plus the GNOME collection in **Settings → Appearance**.
- **Bluetooth:** supported, but **off at startup**, because nearby devices can see a Bluetooth radio. Turn it on from the top-right menu when you need it.
- **Clock:** if the computer's clock is wrong (common on PCs that also run Windows), ASKus corrects it from the Tor network so Tor can connect. Only the system clock is changed, never the hardware clock Windows uses.

## Daily updates (signed)

- **Every day** GitHub builds a fresh ASKus OS with the latest Debian security fixes and Tor Browser, and publishes it under **Releases**. The newest 7 are kept.
- **Every release is signed** with the ASKus release key (`SHA256SUMS.sig`). The matching public key is built into ASKus OS (`/etc/askus/release-signers`), and the updater **refuses any update that isn't signed with it** - a tampered or fake release is never installed. The build refuses to publish if the key is missing. You can also start a build any time: **Actions → Build ASKus OS ISO → Run workflow**.
- **Inside ASKus OS:** about a minute after Tor connects, ASKus OS checks for a newer build. If there is one, a notification offers **Update now**. You can also open **ASKus Update** from the app grid whenever you like.
- **Fast downloads through Tor:** the image is fetched in 32 MB pieces over **several Tor circuits at once** (each piece on its own circuit), which is several times faster than one connection, and an interrupted download resumes where it stopped.
- **Background download:** when Persistent Storage is unlocked, ASKus downloads a new (signed) release quietly in the background, about 10 minutes after startup and then every 6 hours. When it's ready, a notification offers **Install now**, and installing only takes a few minutes.
- **What the update does:** it downloads the new image through Tor (into your Persistent Storage if it's unlocked, otherwise into RAM) checks the signature and the SHA-256. It then moves the running system into memory, writes the new version to the USB stick, reads it back to verify it, and keeps your Persistent Storage. Restart and you're on the new version.
- **Needs:** ASKus OS started from its USB stick and enough free memory (about 3 GB with Persistent Storage unlocked, about 5 GB without). The first 4 GB of the stick are reserved for the system so updates never touch your saved files. That's why Persistent Storage needs a stick of 6 GB or more.

## Everyday Browser (Brave)

For sites where you log in as yourself anyway (business email, banking, YouTube):
- **Brave**, running in a **firejail sandbox**. It can't see your Persistent folder, wallet, GnuPG keys or Tor Browser.
- **Orange window frame**, so you never confuse it with Tor Browser.
- Its traffic **still goes through Tor**, so sites don't see your IP address. Brave's telemetry, Rewards, Wallet, AI chat and built-in Tor windows are switched off.
- **Everyday Browser** forgets everything when you close it. **Everyday Browser (keep logins)** saves logins and bookmarks in your Persistent Storage.
- **Not anonymous:** once you log in, the site knows it's you. Use **Tor Browser** for anything anonymous, and never mix the two for the same task.

## ASKus Assistant (AI)

A chat app in the dock with two modes. The window colour always shows which one you're using:

| Mode | Where it runs | Privacy |
|---|---|---|
| **Claude** (purple) | Anthropic's servers, reached through Tor. Needs an API key from console.anthropic.com. | **Private, not anonymous.** Your IP is hidden, but your API account identifies you. |
| **Local AI** (green) | On your computer with Ollama, completely offline after a one-time download (about 2–7 GB, through Tor). | **Fully private.** Nothing leaves the machine. |

- **Sandboxed** with firejail. It cannot see your Persistent folder, wallet, keys, Tor Browser, Tor settings or USB drives.
- **Files only when you share them.** Put a file in **Shared with AI** (in Files) and click 📎. It reads text, images and PDFs; PDFs work with Claude only.
- **Switching modes starts a new conversation,** so nothing from Local AI is ever sent to Claude.
- The API key and the Local AI live in Persistent Storage when it's unlocked; otherwise they're forgotten at shutdown.
- **Don't paste anything from anonymous Tor sessions into Claude.**

## Automatic program updates

About 1–5 minutes after Tor connects, and then **every 6 hours** while it's running, ASKus OS installs **security fixes, stable updates and Brave updates** in the background, **downloaded through Tor**, so update servers never see your IP address. A notification tells you how many were installed. 
- Core parts (kernel, desktop, boot) aren't changed mid-session. They come with the daily **ASKus Update**, which also makes all updates permanent.
- **Recommended:** let program updates run automatically, and install the **ASKus Update** at least once a week (it's offered daily; the 2.7 GB download over Tor takes a while).
- To turn this off, set `AUTO_UPDATE=no` in `/etc/askus/autoupdate.conf`.

## Leak test

Open **Leak Test** from the app grid (or run `askus-leak-test --text` in a terminal) once Tor is connected. It checks:
- that Tor and the firewall are running
- that apps without proxy settings still exit through Tor, and that the Tor SOCKS proxy works
- that UDP, IPv6 and ping are blocked, and that DNS goes to Tor
- that your network card's MAC address is randomized and the clock is correct
- that AppArmor is on, there's no disk swap, and freed memory is wiped

❌ means a real leak; ⚠️ usually means "Tor still connecting" or "running in a virtual machine".

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
