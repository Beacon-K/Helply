---
title: Can't connect to Wi-Fi
category: Network
audience: everyone
keywords: wifi, wi-fi, wireless, no internet, connected no internet, can't connect, network, hotspot, limited connectivity
summary: Step-by-step fixes when your laptop won't join the Wi-Fi, or says "connected, no internet".
---
## Symptoms

- The Wi-Fi network isn't in the list, or won't connect.
- It says **Connected, no internet** / **No internet, secured**.
- Wi-Fi works on your phone but not on your laptop.

## Quick fixes (try in order)

1. **Is it just you?** If colleagues also have no Wi-Fi, skip to "Whole office down" below.
2. **Turn Wi-Fi off and on.** Click the network icon on the taskbar (Windows) or menu bar (Mac), toggle Wi-Fi off, wait 10 seconds, toggle on.
3. **Check airplane mode is off** and, on some laptops, the physical Wi-Fi switch or `Fn` key.
4. **Restart the laptop** (a real restart, not just closing the lid).
5. **Forget the network and reconnect.**
   - Windows 11: Settings → Network & internet → Wi-Fi → **Manage known networks** → select the network → **Forget**. Then connect again and re-enter the password.
   - Mac: System Settings → Wi-Fi → click `...` next to the network → **Forget This Network**.
6. **Move closer to an access point.** Thick walls, basements and kitchens (microwaves!) weaken the signal.

## "Connected, no internet"

- Open a browser and visit any website. **Hotel, café and guest networks** often show a sign-in page first.
- Run the troubleshooter: Windows 11 Settings → System → Troubleshoot → Other troubleshooters → **Network and Internet**.
- Advanced (Windows): open **Command Prompt** and run `ipconfig /release`, then `ipconfig /renew`, then `ipconfig /flushdns`.
- Last resort on Windows 11: Settings → Network & internet → Advanced network settings → **Network reset** (this removes saved Wi-Fi networks and VPN settings; you'll need to re-enter them).

## Whole office down?

If nobody has internet, it's an outage, not your laptop. Open **one** ticket with **Impact: High, Urgency: High**, and let colleagues add comments to it rather than opening duplicates.

## Still not working?

Open a ticket with:

- Which network name (SSID) you're trying to join and where you are (floor / room).
- Whether other devices work in the same spot.
- A screenshot of any error.
- Whether a wired cable works, if you have a dock or cable handy.
