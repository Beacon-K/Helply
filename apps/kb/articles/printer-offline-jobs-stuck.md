---
title: Printer offline or print jobs stuck in the queue
category: Hardware
audience: everyone
keywords: printer, print, printing, printer offline, not printing, print queue, stuck, pending, spooler, error printing, nothing happens
summary: Get documents printing again when the printer shows "offline" or jobs sit in the queue and nothing comes out.
---
## Check the printer itself

1. Is it **on**, and does its screen show any message (paper jam, out of paper, out of toner, door open)?
2. Look at the printer's display for a **network / Wi-Fi symbol**. If it's disconnected, turn the printer off, wait 30 seconds, and turn it on again.
3. Ask a colleague to try printing. **If nobody can print**, it's the printer or the network, not your computer — open one ticket and mention "everyone affected".

## Printer shows "Offline" on your computer

1. Make sure you're on the **office network** (or connected to the VPN if the printer is at the office and you're not).
2. Windows 11: Settings → Bluetooth & devices → **Printers & scanners** → select the printer → **Open print queue** → click the `...` menu → make sure **Use printer offline** is not ticked.
3. Restart your computer.

## Jobs stuck in the queue

1. Settings → Bluetooth & devices → Printers & scanners → select the printer → **Open print queue**.
2. Right-click each stuck document → **Cancel** (or `...` → **Cancel all**).
3. If a job won't delete, restart your computer — that clears most stuck queues.
4. Print a **short test page** (from the printer's page in Settings → **Print test page**) before sending big documents again.

## Printing the wrong thing, or to the wrong printer

- Check the printer name in the print dialog — Windows may choose the **last used** printer automatically. Turn this off: Settings → Printers & scanners → **Let Windows manage my default printer** → Off, then set your usual printer as default.
- PDFs printing blank or garbled → in the PDF viewer's print dialog, try **Advanced → Print as image**.

## Still not printing?

Open a ticket with the **printer name / location**, whether colleagues can print, the exact error, and a photo of the printer's screen. See also "Print quality problems and paper jams" and "How to add a network printer".
