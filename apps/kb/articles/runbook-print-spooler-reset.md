---
title: "Runbook: clear a stuck print queue (restart the Print Spooler)"
category: Hardware
audience: internal
keywords: runbook, print spooler, stuck print jobs, clear print queue, spooler service, printer driver, remove printer, reinstall driver
summary: Technician steps to clear print jobs that won't delete, restart the Windows Print Spooler, and reinstall a printer driver.
---
## When to use

A user's print jobs won't cancel from the queue, printing hangs for everyone on one PC, or the printer shows errors after a driver update. (User-level steps are in "Printer offline or print jobs stuck in the queue".)

## Clear the spooler (Windows, admin rights)

1. Open **Command Prompt as administrator**.
2. Stop the spooler: `net stop spooler`
3. Delete stuck job files: `del /Q /F %systemroot%\System32\spool\PRINTERS\*`
4. Start the spooler: `net start spooler`
5. Print a test page.

GUI alternative: `services.msc` → **Print Spooler** → Stop → delete the contents of `C:\Windows\System32\spool\PRINTERS` → Start.

## If the spooler keeps crashing

- Usually a **bad printer driver**. Open **Print Management** (`printmanagement.msc`) or Settings → Printers & scanners → **Print server properties** → **Drivers** tab, and remove unused or old drivers.
- Remove the printer, restart, and re-add it with the **manufacturer's current driver** (or the universal driver for that brand).

## Network printer checks

- Ping the printer's IP. No reply → check its network connection / IP (DHCP reservation recommended so the IP doesn't change).
- Print the printer's **configuration page** from its front panel to confirm IP and status.
- If many users are affected, check the print server (if any) and its spooler too.

## Close the ticket

Note what was stuck (driver, spooler, network), what fixed it, and whether a driver standard should change for the fleet.
