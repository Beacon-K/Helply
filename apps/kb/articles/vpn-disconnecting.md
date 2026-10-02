---
title: VPN won't connect or keeps disconnecting
category: Network
audience: everyone
keywords: vpn, remote, work from home, disconnect, disconnecting, drops, can't connect, tunnel, remote access, home office
summary: Fix VPN sign-in failures and connections that keep dropping when working remotely.
---
## Symptoms

- The VPN client says **Connection failed**, **Authentication failed** or times out.
- The VPN connects but drops every few minutes.
- Connected to VPN, but shared drives or internal apps still don't open.

## First, check your home internet

The VPN runs on top of your internet connection — if that's unstable, the VPN will be too.

1. Disconnect the VPN and open a normal website. Does it load quickly?
2. Run a speed test (e.g. search "speed test" in your browser). Under about 5 Mbps upload, or lots of dropouts, and video calls plus VPN will struggle.
3. Restart your home router if the internet itself is flaky (unplug for 30 seconds).

## VPN won't connect

1. **Check your password.** If you changed it recently, the VPN needs the new one. If it's expired, reset it first (see "How to reset a forgotten password").
2. **Approve the MFA prompt** on your phone — the VPN often waits for it silently.
3. **Quit and reopen the VPN client** completely (right-click its icon in the system tray → Exit/Quit).
4. **Restart your laptop.**
5. **Try another network** — a phone hotspot is a good test. If it works there, your home router or ISP is blocking the VPN.
6. Make sure you're on the **latest version** of the VPN client your company provides.

## VPN keeps dropping

- **Use a cable** instead of Wi-Fi if you can, or sit closer to the router.
- **Stop sleep settings from cutting the connection**: plug in to power and avoid closing the lid.
- Pause large personal downloads or streaming on the same home network.
- If it drops at the **same interval every time** (e.g. exactly every hour), note that in your ticket — it points to a server-side timeout IT can check.

## Connected, but can't reach shared drives or apps

1. Wait 30–60 seconds after connecting, then try again.
2. Access the drive using its full path, e.g. `\\fileserver\shared`, instead of the drive letter.
3. Disconnect and reconnect the VPN.

## Still not working?

Open a ticket with:

- The exact error message (screenshot).
- The time it disconnected, as precisely as you can — IT can match it to the VPN server logs.
- Whether it works on a phone hotspot.
- Your internet provider and whether you're on Wi-Fi or cable.
