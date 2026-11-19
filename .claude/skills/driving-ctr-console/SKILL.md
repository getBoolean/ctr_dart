---
name: driving-ctr-console
description: Use when running dartbrew or runtime hardware tests on a real New 3DS-family (CTR) console - arming the Homebrew Launcher netloader remotely (pressing Y/B without touching the console), dismissing netloader errors, uploading with `dartbrew run`/`dartbrew test -d <ip>`, or when a netloader upload fails, is refused, or the console stops answering.
---

# Driving a CTR console for hardware tests

The console runs Luma3DS. Rosalina's **InputRedirection** accepts button presses over UDP, so an agent can press buttons itself instead of asking the user every time. BootNTR adds the NTR debugger (TCP 8000), which is a cheap way to check that the console's network stack is up.

## Prerequisites the user must provide once

- The console's IP address (shown on the Homebrew Launcher netloader screen, or in Rosalina).
- InputRedirection on: Rosalina menu (L + Down + Select) -> Miscellaneous options -> InputRedirection. **It turns off after a reboot or sleep and has to be turned on again.**
- Homebrew Launcher open on the console (the netloader is part of it).
- Windows Firewall allowing the dartbrew executable inbound on TCP and UDP 17491. Windows creates **Block** rules automatically the first time a new exe listens; a moved or rebuilt SDK path gets new rules. Check with `Get-NetFirewallRule -DisplayName dartbrew`.

## Pressing buttons

```bash
python -I .claude/skills/driving-ctr-console/scripts/press.py <console-ip> B Y
```

Each button is held about 150 ms, then released. Buttons: A B X Y L R START SELECT UP DOWN LEFT RIGHT HOME. The packet is the Rosalina/InputRedirectionClient format: five little-endian u32s (pad = 0xfff XOR pressed bits, touch, circle pad, c-stick, interface buttons) to UDP 4950. UDP gives no acknowledgement. The only proof a press landed is what happens next (the netloader accepts a connection, or the user sees it).

## Arming the netloader and uploading

1. `press.py <ip> B Y`. B dismisses a netloader error dialog if one is showing, and Y starts the netloader. Never press A blindly: in the Homebrew Launcher menu it launches the selected app.
2. The netloader takes a moment to start listening. Retry a *refused* connect for a few seconds. A refused connect does not disturb it.
3. Upload: `dartbrew run -d <ip>` or `dartbrew test -d <ip>`. Each upload uses up the netloader; it returns to the menu after the app exits (or after any error), so arm again before every upload.

## Rules learned the hard way

- **Never probe port 17491 with a TCP connect test** (`Test-NetConnection -Port 17491`, `nc -z`). The netloader accepts exactly one connection; a connect that sends nothing fails its first `recv` (the console shows `recv:19`) and returns it to the menu. Ping and NTR's port 8000 are safe checks.
- **Discovery (`dartbrew devices`, `-d console`) only works on the same subnet.** It is a UDP broadcast. When the console is on another subnet (for example PC on 192.168.8.x behind a travel router, console on 192.168.1.x), always pass `-d <ip>`.
- **NAT between PC and console breaks the connect-back.** The console connects back to the address it saw the upload come from. If a router NATs that traffic, the host never sees the connection and `run` exits 1 with the "never connected back / check the firewall" message. Put both on one network, or forward TCP 17491 to the PC.
- **Do not run BootNTR during netloader uploads.** With NTR loaded, uploads failed partway through on the console with `recv:19`, both from dartbrew and from a plain reference uploader. After a reboot without BootNTR, the same upload went through first time. Rosalina InputRedirection is fine to keep on.
- **A separate console subnet behind a NAT router needs a port forward.** The console cannot join a combined 2.4/5 GHz SSID, so it may live on its own network. In the observed setup the PC (192.168.8.30) sits behind router 192.168.8.1, whose WAN side is on the console's network (192.168.1.x, upstream router 192.168.1.254). Uploads work with `-d <ip>`, but the app's connect-back reaches the router's WAN address. Forward WAN TCP 17491 on 192.168.8.1 to 192.168.8.30:17491 (or whichever port `--host-port` uses). `tracert -d <console-ip>` shows the hops.
- **A dropped console** (ping says host unreachable, port 8000 closed) means it slept, lost Wi-Fi or changed address. Ask the user. After it returns, InputRedirection and BootNTR may both need re-enabling.
- Netloader errors on screen read `<function>:<errno>`, from hbmenu's `source/ui/netloader.c` (fincs/new-hbmenu): for example `recv:19`, `chunksize:<n>`, `inflate:<n>`. Read that file before guessing at protocol bugs.
- A console link with 200-700 ms ping is normal for 3DS Wi-Fi. A large JIT app (about 14 MB, 5 MB compressed) takes much longer to upload than on a desktop LAN.
