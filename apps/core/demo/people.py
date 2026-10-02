"""Demo organisation: a ~15-person small business with a 3-person IT team.

Fictional people and company. All demo accounts share DEMO_PASSWORD.
Never load this on a production database.
"""
from datetime import date

DEMO_PASSWORD = "helply-demo-2026"

# username, first, last, role, department, job title
USERS = [
    ("alice", "Alice", "Martin", "supervisor", "IT", "IT Manager"),
    ("tom", "Tom", "Nguyen", "technician", "IT", "Systems Technician"),
    ("tina", "Tina", "Roy", "technician", "IT", "Network Technician"),
    ("sam", "Sam", "Okafor", "technician", "IT", "Service Desk Technician"),
    ("daniel", "Daniel", "Kim", "employee", "Management", "General Manager"),
    ("emma", "Emma", "Clark", "employee", "Finance", "Accountant"),
    ("mia", "Mia", "Patel", "employee", "Finance", "Payroll Coordinator"),
    ("eric", "Eric", "Singh", "employee", "Sales", "Account Executive"),
    ("lucas", "Lucas", "Bouchard", "employee", "Sales", "Sales Representative"),
    ("olivia", "Olivia", "Brown", "employee", "HR", "HR Generalist"),
    ("liam", "Liam", "Tremblay", "employee", "Operations", "Operations Manager"),
    ("chloe", "Chloe", "Lee", "employee", "Operations", "Purchasing Coordinator"),
    ("sophia", "Sophia", "Chen", "employee", "Marketing", "Marketing Specialist"),
    ("noah", "Noah", "Gagnon", "employee", "Warehouse", "Warehouse Lead"),
    ("ava", "Ava", "Wilson", "employee", "Front Office", "Receptionist"),
]

GROUP_MEMBERS = {
    "Service Desk": ["tom", "tina", "sam"],
    "Network & Infrastructure": ["tina"],
    "Applications": ["tom"],
}

# tag, name, type, status, owner username (or None), department, serial, warranty expiry
ASSETS = [
    ("LT-0001", "Dell Latitude 5440", "laptop", "in_use", "emma", "Finance", "DL5440-A1", date(2027, 6, 30)),
    ("LT-0002", "Lenovo ThinkPad T14", "laptop", "in_use", "eric", "Sales", "LTP14-B7", date(2026, 12, 31)),
    ("LT-0003", "Dell Latitude 5440", "laptop", "in_use", "mia", "Finance", "DL5440-C3", date(2027, 6, 30)),
    ("LT-0004", "Lenovo ThinkPad T14", "laptop", "in_use", "lucas", "Sales", "LTP14-D2", date(2026, 12, 31)),
    ("LT-0005", "MacBook Pro 14\" M3", "laptop", "in_use", "sophia", "Marketing", "MBP14-E9", date(2027, 3, 15)),
    ("LT-0006", "Dell Latitude 5430", "laptop", "in_use", "olivia", "HR", "DL5430-F4", date(2026, 2, 28)),
    ("LT-0007", "Lenovo ThinkPad E14", "laptop", "in_use", "liam", "Operations", "LTE14-G1", date(2027, 9, 30)),
    ("LT-0008", "Lenovo ThinkPad E14", "laptop", "in_use", "chloe", "Operations", "LTE14-H6", date(2027, 9, 30)),
    ("LT-0009", "Dell Latitude 7440", "laptop", "in_use", "daniel", "Management", "DL7440-J8", date(2028, 1, 31)),
    ("LT-0010", "Dell Latitude 3420", "laptop", "in_repair", "noah", "Warehouse", "DL3420-K2", date(2025, 11, 30)),
    ("LT-0011", "Lenovo ThinkPad T14 (loaner)", "laptop", "in_use", "noah", "IT", "LTP14-L5", date(2026, 12, 31)),
    ("LT-0012", "Dell Latitude 5440 (spare)", "laptop", "in_stock", None, "IT", "DL5440-X7", date(2028, 6, 30)),
    ("DT-0001", "HP ProDesk 400 G9", "desktop", "in_use", "ava", "Front Office", "HPPD-M3", date(2027, 5, 31)),
    ("MN-0001", "Dell P2723DE 27\" monitor", "monitor", "in_use", "sophia", "Marketing", "DP27-N1", date(2028, 4, 30)),
    ("PR-0001", "HP LaserJet Pro (2nd floor)", "printer", "in_use", None, "Finance", "HPLJ-P7", date(2026, 8, 31)),
    ("PR-0002", "Brother HL-L6210 (front desk)", "printer", "in_use", None, "Front Office", "BRHL-Q4", date(2027, 1, 31)),
    ("PR-0003", "Zebra ZD421 label printer", "printer", "in_use", None, "Warehouse", "ZBZD-R2", date(2027, 7, 31)),
    ("NW-0001", "Fortinet FortiGate 40F firewall", "network", "in_use", None, "IT", "FGT40F-S9", date(2027, 10, 31)),
    ("NW-0002", "Ubiquiti U6 access point (warehouse)", "network", "in_use", None, "Warehouse", "U6AP-T3", None),
    ("OT-0001", "Samsung 65\" boardroom display", "other", "in_use", None, "Management", "SM65-U1", date(2027, 2, 28)),
    ("OT-0002", "Honeywell Voyager barcode scanner", "other", "in_use", "noah", "Warehouse", "HWVY-V6", None),
    ("PH-0001", "iPhone 15 (company phone)", "phone", "in_use", "daniel", "Management", "IP15-W2", date(2026, 10, 31)),
]

ASSET_NOTES = {
    "LT-0001": "Flagged for replacement in next budget round - 4 years old, slow (see ticket history).",
    "LT-0010": "Swollen battery - collected and stored in a fire-safe bag. Out of warranty; replacement recommended.",
    "LT-0011": "Loaner pool. Currently on loan to Noah Gagnon while LT-0010 is out of service.",
    "PR-0001": "Fuser maintenance kit on order (frequent jams).",
    "NW-0002": "Second access point added above the loading dock.",
}
