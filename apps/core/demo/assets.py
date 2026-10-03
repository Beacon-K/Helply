"""Demo asset register for the fictional company: ~100 items a small tech-savvy business owns.

Costs are illustrative estimates in CAD (not quotes). For subscriptions, cost is per year and
warranty_expiry is the renewal date. Tags referenced by the demo tickets (LT-0001 ... PH-0001)
keep their original owners and states so the ticket stories stay consistent.
"""
import hashlib
from dataclasses import dataclass
from datetime import date


@dataclass
class DemoAsset:
    tag: str
    name: str
    type: str
    status: str
    owner: str | None
    department: str
    location: str
    supplier: str
    purchased: date | None
    cost: float | None
    warranty: date | None
    notes: str = ""
    serial: str | None = None

    @property
    def serial_number(self):
        if self.serial is not None:
            return self.serial
        if self.type == "license":
            return ""
        digest = hashlib.md5(self.tag.encode()).hexdigest()[:7].upper()
        return f"{self.tag[:2]}{digest}"


def d(text):
    return date.fromisoformat(text) if text else None


A = DemoAsset
IT, MGMT, FIN, SALES, HR, OPS, MKT, WH, FRONT = (
    "IT", "Management", "Finance", "Sales", "HR", "Operations", "Marketing", "Warehouse", "Front Office")
DELL, LENOVO, APPLE, CDW, AMZ = "Dell Canada", "Lenovo Canada", "Apple Store for Business", "CDW Canada", "Amazon Business"

ASSETS = [
    # --- Laptops ------------------------------------------------------------------------------
    A("LT-0001", "Dell Latitude 5440", "laptop", "in_use", "emma", FIN, "HQ 2F - Finance", DELL, d("2022-06-30"), 1650, d("2027-06-30"),
      "Flagged for replacement in next budget round - 4 years old, slow (see ticket history).", "DL5440-A1"),
    A("LT-0002", "Lenovo ThinkPad T14", "laptop", "in_use", "eric", SALES, "HQ 1F - Sales", LENOVO, d("2023-12-15"), 1800, d("2026-12-31"), serial="LTP14-B7"),
    A("LT-0003", "Dell Latitude 5440", "laptop", "in_use", "mia", FIN, "HQ 2F - Finance", DELL, d("2024-06-28"), 1650, d("2027-06-30"), serial="DL5440-C3"),
    A("LT-0004", "Lenovo ThinkPad T14", "laptop", "in_use", "lucas", SALES, "Remote / travelling", LENOVO, d("2023-12-15"), 1800, d("2026-12-31"),
      "Screen replaced under accidental damage cover.", "LTP14-D2"),
    A("LT-0005", "MacBook Pro 14\" M3", "laptop", "in_use", "sophia", MKT, "HQ 2F - Marketing", APPLE, d("2024-03-15"), 3100, d("2027-03-15"), serial="MBP14-E9"),
    A("LT-0006", "Dell Latitude 5430", "laptop", "in_use", "olivia", HR, "HQ 2F - HR", DELL, d("2023-02-28"), 1550, d("2026-02-28"), serial="DL5430-F4"),
    A("LT-0007", "Lenovo ThinkPad E14", "laptop", "in_use", "liam", OPS, "HQ 1F - Operations", LENOVO, d("2024-09-30"), 1300, d("2027-09-30"), serial="LTE14-G1"),
    A("LT-0008", "Lenovo ThinkPad E14", "laptop", "in_use", "chloe", OPS, "HQ 1F - Operations", LENOVO, d("2024-09-30"), 1300, d("2027-09-30"), serial="LTE14-H6"),
    A("LT-0009", "Dell Latitude 7440", "laptop", "in_use", "daniel", MGMT, "HQ 2F - Management", DELL, d("2025-01-31"), 2300, d("2028-01-31"), serial="DL7440-J8"),
    A("LT-0010", "Dell Latitude 3420", "laptop", "in_repair", "noah", WH, "IT storeroom", DELL, d("2021-11-30"), 1100, d("2025-11-30"),
      "Swollen battery - collected and stored in a fire-safe bag. Out of warranty; replacement recommended.", "DL3420-K2"),
    A("LT-0011", "Lenovo ThinkPad T14 (loaner)", "laptop", "in_use", "noah", IT, "Warehouse", LENOVO, d("2023-12-15"), 1800, d("2026-12-31"),
      "Loaner pool. Currently on loan to Noah Gagnon while LT-0010 is out of service.", "LTP14-L5"),
    A("LT-0012", "Dell Latitude 5440 (spare)", "laptop", "in_stock", None, IT, "IT storeroom", DELL, d("2025-06-30"), 1650, d("2028-06-30"), serial="DL5440-X7"),
    A("LT-0013", "MacBook Pro 14\" M3 Pro", "laptop", "in_use", "alice", IT, "HQ 2F - IT office", APPLE, d("2025-02-10"), 3400, d("2028-02-10")),
    A("LT-0014", "Lenovo ThinkPad P1 Gen 6", "laptop", "in_use", "tom", IT, "HQ 2F - IT office", LENOVO, d("2024-08-20"), 3200, d("2027-08-20")),
    A("LT-0015", "Dell Precision 5680", "laptop", "in_use", "tina", IT, "HQ 2F - IT office", DELL, d("2024-11-05"), 3500, d("2027-11-05")),
    A("LT-0016", "Lenovo ThinkPad T14 Gen 4", "laptop", "in_use", "sam", IT, "HQ 2F - IT office", LENOVO, d("2025-03-03"), 1850, d("2028-03-03")),
    A("LT-0017", "Dell Latitude 5490", "laptop", "retired", None, IT, "IT storeroom", DELL, d("2019-05-14"), 1400, d("2022-05-14"),
      "Retired Aug 2026. Drive wiped (certificate on file); awaiting e-waste pickup."),
    A("LT-0018", "MacBook Air 13\" M2 (spare)", "laptop", "in_stock", None, IT, "IT storeroom", APPLE, d("2023-09-01"), 1450, d("2026-09-01")),

    # --- Desktops / workstations --------------------------------------------------------------
    A("DT-0001", "HP ProDesk 400 G9", "desktop", "in_use", "ava", FRONT, "HQ 1F - Front desk", CDW, d("2024-05-31"), 1050, d("2027-05-31"),
      "Power supply replaced under warranty.", "HPPD-M3"),
    A("DT-0002", "Dell OptiPlex 7010 (shipping station)", "desktop", "in_use", None, WH, "Warehouse - Shipping station", DELL, d("2023-04-18"), 980, d("2026-04-18"),
      "Prints shipping labels on PR-0003."),
    A("DT-0003", "Lenovo ThinkCentre M70q (warehouse office)", "desktop", "in_use", None, WH, "Warehouse", LENOVO, d("2024-06-10"), 850, d("2027-06-10")),
    A("DT-0004", "Dell Precision 3660 (imaging station)", "desktop", "in_use", None, IT, "HQ 2F - IT office", DELL, d("2023-10-28"), 2400, d("2026-10-28"),
      "Used to image and prepare new laptops."),

    # --- Monitors -------------------------------------------------------------------------------
    A("MN-0001", "Dell P2723DE 27\" monitor", "monitor", "in_use", "sophia", MKT, "HQ 2F - Marketing", DELL, d("2025-04-30"), 520, d("2028-04-30"), serial="DP27-N1"),
    A("MN-0002", "Dell UltraSharp U2723QE 27\" 4K", "monitor", "in_use", "alice", IT, "HQ 2F - IT office", DELL, d("2025-02-10"), 780, d("2028-02-10")),
    A("MN-0003", "Dell UltraSharp U2723QE 27\" 4K", "monitor", "in_use", "alice", IT, "HQ 2F - IT office", DELL, d("2025-02-10"), 780, d("2028-02-10")),
    A("MN-0004", "Dell UltraSharp U2723QE 27\" 4K", "monitor", "in_use", "tom", IT, "HQ 2F - IT office", DELL, d("2024-08-20"), 780, d("2027-08-20")),
    A("MN-0005", "Dell UltraSharp U2723QE 27\" 4K", "monitor", "in_use", "tom", IT, "HQ 2F - IT office", DELL, d("2024-08-20"), 780, d("2027-08-20")),
    A("MN-0006", "LG 34WP65C 34\" UltraWide", "monitor", "in_use", "tina", IT, "HQ 2F - IT office", CDW, d("2024-11-05"), 600, d("2026-11-05")),
    A("MN-0007", "Dell P2423D 24\" QHD", "monitor", "in_use", "sam", IT, "HQ 2F - IT office", DELL, d("2025-03-03"), 330, d("2028-03-03")),
    A("MN-0008", "Dell UltraSharp U2723QE 27\" 4K", "monitor", "in_use", "daniel", MGMT, "HQ 2F - Management", DELL, d("2025-01-31"), 780, d("2028-01-31")),
    A("MN-0009", "Dell P2423D 24\" QHD", "monitor", "in_use", "emma", FIN, "HQ 2F - Finance", DELL, d("2023-03-14"), 330, d("2026-03-14")),
    A("MN-0010", "Dell P2423D 24\" QHD", "monitor", "in_use", "mia", FIN, "HQ 2F - Finance", DELL, d("2024-06-28"), 330, d("2027-06-28")),
    A("MN-0011", "Dell P2423D 24\" QHD", "monitor", "in_use", "eric", SALES, "HQ 1F - Sales", DELL, d("2023-12-15"), 330, d("2026-12-15")),
    A("MN-0012", "Dell P2423D 24\" QHD", "monitor", "in_use", "lucas", SALES, "HQ 1F - Sales", DELL, d("2023-12-15"), 330, d("2026-12-15")),
    A("MN-0013", "Dell P2423D 24\" QHD", "monitor", "in_use", "olivia", HR, "HQ 2F - HR", DELL, d("2023-02-28"), 330, d("2026-02-28")),
    A("MN-0014", "Dell P2723D 27\" QHD", "monitor", "in_use", "liam", OPS, "HQ 1F - Operations", DELL, d("2024-09-30"), 420, d("2027-09-30")),
    A("MN-0015", "Dell P2423D 24\" QHD", "monitor", "in_use", "chloe", OPS, "HQ 1F - Operations", DELL, d("2024-09-30"), 330, d("2027-09-30")),
    A("MN-0016", "Dell P2423D 24\" QHD", "monitor", "in_use", "ava", FRONT, "HQ 1F - Front desk", DELL, d("2024-05-31"), 330, d("2027-05-31")),
    A("MN-0017", "Dell P2423D 24\" QHD (spare)", "monitor", "in_stock", None, IT, "IT storeroom", DELL, d("2025-03-03"), 330, d("2028-03-03")),
    A("MN-0018", "Samsung S22F350 22\"", "monitor", "retired", None, IT, "IT storeroom", AMZ, d("2018-10-02"), 160, d("2020-10-02"),
      "Retired - flickering backlight. Awaiting e-waste pickup."),

    # --- Peripherals / accessories --------------------------------------------------------------
    A("PE-0001", "Dell WD19S USB-C dock", "peripheral", "in_use", "emma", FIN, "HQ 2F - Finance", DELL, d("2022-06-30"), 290, d("2025-06-30"),
      "Firmware outdated - update booked (see ticket 'Laptop screen flickering with dock')."),
    A("PE-0002", "Dell WD19S USB-C dock", "peripheral", "in_use", "mia", FIN, "HQ 2F - Finance", DELL, d("2024-06-28"), 290, d("2027-06-28")),
    A("PE-0003", "Dell WD22TB4 Thunderbolt dock", "peripheral", "in_use", "daniel", MGMT, "HQ 2F - Management", DELL, d("2025-01-31"), 420, d("2028-01-31")),
    A("PE-0004", "Lenovo USB-C Dock Gen 2", "peripheral", "in_use", "eric", SALES, "HQ 1F - Sales", LENOVO, d("2023-12-15"), 260, d("2026-12-15")),
    A("PE-0005", "Lenovo USB-C Dock Gen 2", "peripheral", "in_use", "liam", OPS, "HQ 1F - Operations", LENOVO, d("2024-09-30"), 260, d("2027-09-30")),
    A("PE-0006", "Lenovo USB-C Dock Gen 2", "peripheral", "in_use", "chloe", OPS, "HQ 1F - Operations", LENOVO, d("2024-09-30"), 260, d("2027-09-30")),
    A("PE-0007", "CalDigit TS4 Thunderbolt dock", "peripheral", "in_use", "alice", IT, "HQ 2F - IT office", CDW, d("2025-02-10"), 480, d("2027-02-10")),
    A("PE-0008", "Lenovo ThinkPad Thunderbolt 4 dock", "peripheral", "in_use", "tom", IT, "HQ 2F - IT office", LENOVO, d("2024-08-20"), 390, d("2027-08-20")),
    A("PE-0009", "Dell WD22TB4 Thunderbolt dock", "peripheral", "in_use", "tina", IT, "HQ 2F - IT office", DELL, d("2024-11-05"), 420, d("2027-11-05")),
    A("PE-0010", "Lenovo USB-C Dock Gen 2 (spare)", "peripheral", "in_stock", None, IT, "IT storeroom", LENOVO, d("2025-03-03"), 260, d("2028-03-03")),
    A("PE-0011", "Jabra Evolve2 65 headset", "peripheral", "in_use", "eric", SALES, "HQ 1F - Sales", CDW, d("2024-01-08"), 330, d("2026-01-08")),
    A("PE-0012", "Jabra Evolve2 65 headset", "peripheral", "in_use", "lucas", SALES, "Remote / travelling", CDW, d("2024-01-08"), 330, d("2026-01-08")),
    A("PE-0013", "Jabra Evolve2 40 headset", "peripheral", "in_use", "ava", FRONT, "HQ 1F - Front desk", CDW, d("2024-05-31"), 170, None),
    A("PE-0014", "Jabra Evolve2 40 headset", "peripheral", "in_use", "mia", FIN, "HQ 2F - Finance", CDW, d("2026-09-28"), 170, d("2028-09-28"),
      "Provided to fix echo in Teams calls."),
    A("PE-0015", "Jabra Evolve2 65 headset", "peripheral", "in_use", "sam", IT, "HQ 2F - IT office", CDW, d("2025-03-03"), 330, d("2027-03-03")),
    A("PE-0016", "Jabra Evolve2 65 headset (spare)", "peripheral", "in_stock", None, IT, "IT storeroom", CDW, d("2025-03-03"), 330, d("2027-03-03")),
    A("PE-0017", "Poly Voyager Focus 2 headset", "peripheral", "in_repair", "olivia", HR, "IT storeroom", CDW, d("2024-07-15"), 380, d("2026-07-15"),
      "Left ear cup crackles - warranty claim submitted before expiry."),
    A("PE-0018", "YubiKey 5 NFC security key", "peripheral", "in_use", "alice", IT, "HQ 2F - IT office", AMZ, d("2025-02-10"), 75, None, "Admin accounts require a hardware key."),
    A("PE-0019", "YubiKey 5 NFC security key", "peripheral", "in_use", "tom", IT, "HQ 2F - IT office", AMZ, d("2025-02-10"), 75, None),
    A("PE-0020", "YubiKey 5 NFC security key", "peripheral", "in_use", "tina", IT, "HQ 2F - IT office", AMZ, d("2025-02-10"), 75, None),
    A("PE-0021", "YubiKey 5 NFC security key", "peripheral", "in_use", "sam", IT, "HQ 2F - IT office", AMZ, d("2025-03-03"), 75, None),
    A("PE-0022", "YubiKey 5 NFC security key", "peripheral", "in_use", "daniel", MGMT, "HQ 2F - Management", AMZ, d("2025-02-10"), 75, None),
    A("PE-0023", "YubiKey 5 NFC security key (spare)", "peripheral", "in_stock", None, IT, "IT storeroom", AMZ, d("2025-03-03"), 75, None),
    A("PE-0024", "Logitech MX Keys + MX Master 3S", "peripheral", "in_use", "sophia", MKT, "HQ 2F - Marketing", AMZ, d("2024-03-15"), 260, None),
    A("PE-0025", "Logitech MX Keys + MX Master 3S", "peripheral", "in_use", "alice", IT, "HQ 2F - IT office", AMZ, d("2025-02-10"), 260, None),
    A("PE-0026", "Logitech MK540 keyboard + mouse", "peripheral", "in_use", "ava", FRONT, "HQ 1F - Front desk", AMZ, d("2024-05-31"), 70, None),
    A("PE-0027", "Logitech Brio 4K webcam", "peripheral", "in_use", "daniel", MGMT, "HQ 2F - Management", AMZ, d("2025-01-31"), 260, d("2027-01-31")),

    # --- Phones and tablets ------------------------------------------------------------------------
    A("PH-0001", "iPhone 15 (company phone)", "phone", "in_use", "daniel", MGMT, "HQ 2F - Management", "Bell Business", d("2024-10-31"), 1250, d("2026-10-31"), serial="IP15-W2"),
    A("PH-0002", "iPhone 14 (company phone)", "phone", "in_use", "eric", SALES, "HQ 1F - Sales", "Bell Business", d("2023-11-20"), 1000, d("2025-11-20")),
    A("PH-0003", "iPhone 15 (company phone)", "phone", "in_use", "lucas", SALES, "Remote / travelling", "Bell Business", d("2024-10-31"), 1250, d("2026-10-31")),
    A("PH-0004", "Samsung Galaxy A35 (IT on-call phone)", "phone", "in_use", None, IT, "HQ 2F - IT office", "Rogers for Business", d("2024-04-15"), 450, d("2026-04-15"),
      "Shared on-call phone - passed to the technician on call each week."),
    A("TB-0001", "iPad 10th gen (inventory scanning)", "tablet", "in_use", None, WH, "Warehouse", APPLE, d("2024-03-05"), 600, d("2027-03-05"),
      "AppleCare+ for Business (3 years)."),
    A("TB-0002", "iPad 10th gen (inventory scanning)", "tablet", "in_use", None, WH, "Warehouse", APPLE, d("2024-03-05"), 600, d("2027-03-05"),
      "AppleCare+ for Business (3 years)."),
    A("TB-0003", "iPad 10th gen (visitor sign-in)", "tablet", "in_use", None, FRONT, "HQ 1F - Front desk", APPLE, d("2023-06-12"), 600, d("2025-06-12")),

    # --- Printers / scanners -----------------------------------------------------------------------
    A("PR-0001", "HP LaserJet Pro (2nd floor)", "printer", "in_use", None, FIN, "HQ 2F - Print corner", CDW, d("2023-08-31"), 650, d("2026-08-31"),
      "Fuser maintenance kit on order (frequent jams).", "HPLJ-P7"),
    A("PR-0002", "Brother HL-L6210 (front desk)", "printer", "in_use", None, FRONT, "HQ 1F - Front desk", "Staples Business", d("2024-01-31"), 480, d("2027-01-31"), serial="BRHL-Q4"),
    A("PR-0003", "Zebra ZD421 label printer", "printer", "in_use", None, WH, "Warehouse - Shipping station", CDW, d("2025-07-31"), 780, d("2027-07-31"),
      "DHCP reservation set after the IP changed during a power cut.", "ZBZD-R2"),
    A("PR-0004", "Fujitsu ScanSnap iX1600 scanner", "printer", "in_use", None, FIN, "HQ 2F - Finance", CDW, d("2024-01-22"), 560, d("2025-01-22")),
    A("PR-0005", "HP OfficeJet Pro 9015", "printer", "retired", None, IT, "IT storeroom", "Staples Business", d("2020-02-11"), 330, d("2021-02-11"),
      "Replaced by PR-0001. Awaiting e-waste pickup."),

    # --- Servers and storage -------------------------------------------------------------------------
    A("SV-0001", "Dell PowerEdge T350 (file server)", "server", "in_use", None, IT, "Server room", DELL, d("2022-08-15"), 5200, d("2027-08-15"),
      "Hosts the S: shared drive and the QuickBooks company file. Windows updates run on weekends."),
    A("SV-0002", "Intel NUC 13 Pro (monitoring & print server)", "server", "in_use", None, IT, "Server room", CDW, d("2024-02-01"), 900, d("2027-02-01")),
    A("ST-0001", "Synology DS923+ NAS (4 x 8 TB)", "storage", "in_use", None, IT, "Server room", CDW, d("2023-03-20"), 2100, d("2026-03-20"),
      "Nightly backup of the file server; snapshots every 2 hours. Used to restore 'Supplier Contracts 2025'."),
    A("ST-0002", "Synology DS223 (offsite backup)", "storage", "in_use", None, IT, "Offsite backup location", CDW, d("2024-05-02"), 650, d("2027-05-02"),
      "Receives encrypted replication from ST-0001 every night."),
    A("ST-0003", "WD Elements 5 TB external drive", "storage", "in_stock", None, IT, "IT storeroom", AMZ, d("2025-01-10"), 170, d("2027-01-10"),
      "Monthly offline backup rotation."),

    # --- Network -------------------------------------------------------------------------------------
    A("NW-0001", "Fortinet FortiGate 40F firewall", "network", "in_use", None, IT, "Server room", "NetSecure Inc. (Fortinet partner)", d("2024-10-31"), 950, d("2027-10-31"),
      serial="FGT40F-S9"),
    A("NW-0002", "Ubiquiti U6 access point (warehouse)", "network", "in_use", None, WH, "Warehouse", CDW, d("2023-05-10"), 230, None,
      "Second access point added above the loading dock (NW-0005).", "U6AP-T3"),
    A("NW-0003", "Ubiquiti U6 Pro access point (1F)", "network", "in_use", None, IT, "HQ 1F - ceiling", CDW, d("2023-05-10"), 260, d("2025-05-10")),
    A("NW-0004", "Ubiquiti U6 Pro access point (2F)", "network", "in_use", None, IT, "HQ 2F - ceiling", CDW, d("2023-05-10"), 260, d("2025-05-10")),
    A("NW-0005", "Ubiquiti U6 access point (loading dock)", "network", "in_use", None, WH, "Warehouse - Loading dock", CDW, d("2026-09-14"), 230, d("2027-09-14"),
      "Added after the 'Wi-Fi drops near the loading dock' ticket."),
    A("NW-0006", "Ubiquiti USW-Pro-24-PoE switch (core)", "network", "in_use", None, IT, "Server room", CDW, d("2023-05-10"), 1100, d("2025-05-10")),
    A("NW-0007", "Ubiquiti USW-Lite-8-PoE switch", "network", "in_use", None, WH, "Warehouse", CDW, d("2023-05-10"), 160, d("2025-05-10")),
    A("NW-0008", "Peplink Balance 20X (LTE backup router)", "network", "in_use", None, IT, "Server room", CDW, d("2024-06-03"), 900, d("2027-06-03"),
      "Failover internet - kept email and Teams working during the fibre cut (P1 ticket)."),

    # --- Power ---------------------------------------------------------------------------------------
    A("PW-0001", "APC Smart-UPS 1500VA (server rack)", "power", "in_use", None, IT, "Server room", CDW, d("2022-08-15"), 1300, d("2025-08-15"),
      "Battery replaced Aug 2025. Next battery check Aug 2027."),
    A("PW-0002", "APC Back-UPS Pro 1000 (network closet)", "power", "in_use", None, IT, "Network closet 1F", CDW, d("2023-05-10"), 260, d("2026-05-10")),

    # --- Meeting rooms / AV ----------------------------------------------------------------------------
    A("OT-0001", "Samsung 65\" boardroom display", "av", "in_use", None, MGMT, "Boardroom", CDW, d("2024-02-28"), 1400, d("2027-02-28"),
      "HDMI cable damaged - USB-C adapter in use until the new cable arrives.", "SM65-U1"),
    A("AV-0001", "Logitech Rally Bar (boardroom camera)", "av", "in_use", None, MGMT, "Boardroom", CDW, d("2024-02-28"), 4500, d("2027-02-28"),
      "Logitech extended warranty (+1 year)."),
    A("AV-0002", "Jabra Speak2 75 speakerphone", "av", "in_use", None, OPS, "Huddle room", CDW, d("2024-09-10"), 380, d("2026-09-10")),
    A("AV-0003", "LG 55\" display (huddle room)", "av", "in_use", None, OPS, "Huddle room", CDW, d("2023-11-12"), 900, d("2026-11-12")),

    # --- Other -----------------------------------------------------------------------------------------
    A("OT-0002", "Honeywell Voyager barcode scanner", "other", "in_use", "noah", WH, "Warehouse", CDW, d("2022-09-12"), 260, None, serial="HWVY-V6"),

    # --- Software licences and subscriptions (cost = per year, warranty = renewal date) ------------------
    A("LC-0001", "Microsoft 365 Business Premium (20 seats)", "license", "in_use", None, IT, "Cloud", "Microsoft", d("2025-11-01"), 7200, d("2026-11-01"),
      "Includes Exchange, Teams, OneDrive, Intune and Defender for Business."),
    A("LC-0002", "Adobe Creative Cloud All Apps (1 seat)", "license", "in_use", None, MKT, "Cloud", "Adobe", d("2026-09-08"), 1100, d("2027-09-08"),
      "Bought for the new designer (approved by Daniel)."),
    A("LC-0003", "QuickBooks Enterprise (3 users)", "license", "in_use", None, FIN, "Server room (SV-0001)", "Intuit Canada", d("2026-01-15"), 3600, d("2027-01-15")),
    A("LC-0004", "HubSpot Sales Hub Professional (5 seats)", "license", "in_use", None, SALES, "Cloud", "HubSpot", d("2026-03-01"), 6000, d("2027-03-01")),
    A("LC-0005", "1Password Business (20 seats)", "license", "in_use", None, IT, "Cloud", "1Password", d("2026-06-01"), 2300, d("2027-06-01")),
    A("LC-0006", "FortiGate UTP security subscription", "license", "in_use", None, IT, "Server room (NW-0001)", "NetSecure Inc. (Fortinet partner)", d("2024-10-31"), 1100, d("2027-10-31"),
      "Web filtering, antivirus and intrusion prevention for the firewall (3-year term)."),
    A("LC-0007", "Windows Server 2022 Standard (16 cores)", "license", "in_use", None, IT, "Server room (SV-0001)", CDW, d("2022-08-15"), 1400, None,
      "Perpetual licence - no renewal."),
]
